import praw
import pprint
from praw.models import MoreComments
from collections import defaultdict
import re
import argparse
from collections import namedtuple
import logging
import datetime

"""
Resources:
    - https://praw.readthedocs.io/en/latest/tutorials/comments.html


What would we like to know? We want to measure hype.
We can be pretty creative with the metrics we want to use.
For a submissions with certain tickers in the title:
    - How many comments does it have?
    - How many upvotes does the submission have?
    - How does an "hype" metric.


V1:
    - Count the occurence of tickers in a submission.
    - Ticker is only counted once per comment.
    - Specify submission with command line arg.


V2:
    - Allow multiple submissions to be specified and parsed.

V3:
    - For a ticker that appears in a submission,
    - Count the number of comments it has.
    - Aggregate the ticker count over many submissions.
    - Also note the upvote score for submissions.
    - Coin this metrics as: ticker induced comments.
"""

_MAX_TICKER_LEN = 5

# TODO: Maybe put these in a file instead?
_TICKER_BLACK_LIST = {
    "I",
    "DD",
    "FUCK",
    "WSB",
    "IPO",
    "LOL",
    "BEARS",
    "EOW",
    "BBQ",
    "MOON",
    "SHORT",
    "SEC",
    "AND",
    "IS",
    "YOU",
    "SHIT",
    "SPY",
    "WE",
    "SEC",
    "ITM",
    "OTM",
    "EOY",
    "A",
    "RIP",
    "FOR",
    "SO",
    "FOMO",
}

_HEADER = "=================================\n"

# TODO: Use a mapping between tickers and company names.
_TICKER_WEIGHT_THRESH = 0.01
_TICKER_COUNT_THRESH = 2

_delimiters = "|".join([
    "\s",
    ",",
    "\.",
    ";",
    "\:",
    "\?",
    "!", 
])
_delim_reg = re.compile(_delimiters)


_ticker_reg = re.compile(r"^\$?[A-Z]+$")
def word_is_ticker(word):
    res = _ticker_reg.match(word)
    if res is None:
        return False
    normalized = normalize_ticker(word)
    if len(normalized) > _MAX_TICKER_LEN:
        return False
    if normalized in _TICKER_BLACK_LIST:
        return False
    return True


def get_agg_ticker_count(ticker_counts):
    agg = 0
    for t, c in ticker_counts.items():
        agg += c
    return agg
        

def filter_ticker_counts(ticker_counts):
    ret = {}
    agg = get_agg_ticker_count(ticker_counts)
    for t, c in ticker_counts.items():
        if c <= _TICKER_COUNT_THRESH:
            continue
        if (c / agg) < _TICKER_WEIGHT_THRESH:
            continue
        ret[t] = c
    return ret


def normalize_ticker(word):
    if word.startswith("$"):
        word = word[1:]
    return word


def extract_tickers_from_text(text):
    ticker_set = set()
    words = _delim_reg.split(text)
    for w in words:
        if word_is_ticker(w):
            ticker_set.add(w)
    return ticker_set


def set_to_count(s):
    d = {
        k : 1
        for k in s
    }
    return d


def extract_tickers_from_submission_content(submission):
    """Does not look at the comments"""
    ticker_set = set()
    ret = ticker_set \
        .union(extract_tickers_from_text(submission.name))      \
        .union(extract_tickers_from_text(submission.title))     \
        .union(extract_tickers_from_text(submission.selftext))
    return ret


def merge_word_counts(acquirer, acquiree):
    for w in acquiree:
        acquirer[w] += acquiree[w]


SubmissionResults = namedtuple(
    "SubmissionResults",
    "ticker_counts comment_count submission"
)


def count_ticker_induced_comments(submission):
    post_ticker_set = extract_tickers_from_submission_content(submission)
    post_ticker_count = set_to_count(post_ticker_set)
    for t in post_ticker_count:
        post_ticker_count[t] = submission.num_comments
    return post_ticker_count


def scrape_submission(submission,
    comment_expansion_limit=0,
    comment_expansion_thresh=1):
    submission_ticker_count = defaultdict(int)

    post_ticker_set = extract_tickers_from_submission_content(submission)
    merge_word_counts(
        submission_ticker_count,
        set_to_count(post_ticker_set)
    )

    comment_forest = submission.comments

    # Expand MoreComment instances in the CommentForest. 
    comment_forest.replace_more(
        # Setting to None means full expansion, 0 means no expansion.
        limit=comment_expansion_limit,
        # Only replace instances that expand to a min n.o. comments.
        threshold=comment_expansion_thresh,
    )

    # Do BFS traversal of CommentForest.
    comment_count = 0
    for comment in submission.comments.list():
        comment_ticker_set = extract_tickers_from_text(comment.body)
        comment_ticker_count = set_to_count(comment_ticker_set)
        merge_word_counts(submission_ticker_count, comment_ticker_count)
        comment_count += 1

    # Sort it now so we don't have to sort later.
    # TODO: Use a map semantic instead?
    submission_ticker_count = filter_ticker_counts(submission_ticker_count)
    submission_ticker_count = sort_ticker_counts(submission_ticker_count)
    res = SubmissionResults(
        ticker_counts=submission_ticker_count,
        comment_count=comment_count,
        submission=submission,)
    return res


def scrape_subreddit(subreddit):
    for submission in subreddit.hot(limit=1):
        submission_ticker_count = scrape_submission(submission)
        

def sort_ticker_counts(ticker_counts):
    ret = {
        k: v
        for k, v in sorted(
            ticker_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    }
    return ret

def format_ticker_counts(ticker_counts):
    tc_s = sort_ticker_counts(ticker_counts)
    fstr = "\n".join(f"\t{k}: {v}" for k, v in tc_s.items())
    return fstr

def format_ticker_count_per_comment(ticker_counts):
    tc_s = sort_ticker_counts(ticker_counts)
    fstr = "\n".join(f"\t{k}: {v:.2f}" for k, v in tc_s.items())
    return fstr

def normalize_ticker_count_per_comment(ticker_counts, num_comments):
    ret = {
        t : 100 * c / num_comments
        for t, c in ticker_counts.items()
    }
    return ret

def write_submission_result(f, res):
    logging.info(f"Writing submission results to {f.name}")       
    f.write(
        f"Submission Title: {res.submission.title}\n"
        f"Submission URL: {res.submission.url}\n"
        f"Submission ID: {res.submission.id}\n"
        f"Comments Parsed: {res.comment_count}\n"
        f"Ticker Counts:\n"
        f"{format_ticker_counts(res.ticker_counts)}\n"
    )

    normalized_tc = normalize_ticker_count_per_comment(
        res.ticker_counts,
        res.comment_count
    )
    normalized_tc_str = format_ticker_count_per_comment(normalized_tc)
    f.write(f"Ticker Occurence / Comment:\n{normalized_tc_str}\n")
    f.write(f"{_HEADER}")
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--submission",
        type=str,
        nargs="+",
        help="Submission ID (e.g k29omq)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="File to write results to",
        default="out.txt"
    )
    parser.add_argument(
        "-c",
        "--cache",
        type=str,
        help="Cache results to a file",
        default=None,
    )
    parser.add_argument(
        "-e",
        "--expansion_limit",
        type=int,
        help="Comment expansion limit, None to expand everything",
        default=None,
    )
    args = parser.parse_args()
    
    logging.basicConfig(
        filename="wsb_scraper.log",
        level=logging.DEBUG
    )
    with open("wsb_scraper.log", "w") as f:
        f.write("")

    reddit = praw.Reddit(
        client_id="Q0GxKcurTVudUQ",
        client_secret="gNij1LOfLX-gfUF_al-XTk-JU0ADFQ",
        user_agent="jesuspwndu",
        #username="my username",
        #password="my password"
    )
    wsb = reddit.subreddit("wallstreetbets")

    # If file does not exist create it. If it does exist, overwrite.
    with open(args.output, "w") as f:
        f.write(f"{datetime.datetime.now()}\n")
        f.write(_HEADER)

        logging.info(f"Submissions: {args.submission}")

        ticker_induced_comment_count = defaultdict(int)
        for submission_id in args.submission:
            submission = reddit.submission(id=submission_id)
            res = scrape_submission(
                submission,
                comment_expansion_limit=args.expansion_limit,
            )
            write_submission_result(f, res)

            merge_word_counts(
                ticker_induced_comment_count,
                count_ticker_induced_comments(submission)
            )

        f.write(
            f"Ticker Induced Comment Count:\n"
            f"{format_ticker_counts(ticker_induced_comment_count)}\n"
            f"{_HEADER}"
        )


if __name__ == "__main__":
    main()

