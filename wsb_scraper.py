import praw
import pprint
from praw.models import MoreComments
from collections import defaultdict
import re
import argparse
from collections import namedtuple
import logging


"""
Resources:
    - https://praw.readthedocs.io/en/latest/tutorials/comments.html


What would we like to know? We want to measure hype.
We can be pretty creative with the metrics we want to use.
For a submissions with certain tickers in the title:
    - How many comments does it have?
    - How many upvotes does the submission have?
    - How does an "hype" metric.


Prototype 1:
    - Count the occurence of tickers in a submission.
    - Ticker is only counted once per comment.
    - Specify submission with command line arg.


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

_TICKER_WEIGHT_THRESH = 0.01
_TICKER_COUNT_THRESH = 5

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
    ticker_set.union(extract_tickers_from_text(submission.name))
    ticker_set.union(extract_tickers_from_text(submission.title))
    ticker_set.union(extract_tickers_from_text(submission.selftext))
    return ticker_set


def merge_word_counts(acquirer, acquiree):
    for w in acquiree:
        acquirer[w] += acquiree[w]


SubmissionResults = namedtuple(
    "SubmissionResults",
    "ticker_counts comment_count submission")


def scrape_submission(submission,
    comment_expansion_limit=0,
    comment_expansion_thresh=1):
    submission_ticker_count = defaultdict(int)

    post_ticker_set = extract_tickers_from_submission_content(submission)
    post_ticker_count = set_to_count(post_ticker_set)
    merge_word_counts(submission_ticker_count, post_ticker_count)

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
        print(submission_ticker_count)
        

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
    fstr = "\n".join(f"{k}: {v}" for k, v in tc_s.items())
    return fstr

def normalize_ticker_count_per_comment(ticker_counts, num_comments):
    ret = {
        t : c / num_comments
        for t, c in ticker_counts.items()
    }
    return ret

def write_submission_result(fname, res):
    with open(fname, "w") as f:
        f.write(f"Submission Title: {res.submission.title}\n")
        f.write(f"Submission URL: {res.submission.url}\n")
        f.write(f"Comments Parsed: {res.comment_count}\n")
        f.write(f"Ticker Counts:\n{format_ticker_counts(res.ticker_counts)}\n")
        normalized_tc = normalize_ticker_count_per_comment(
            res.ticker_counts,
            res.comment_count
        )
        f.write(f"Ticker Occurence / Comment:\n{format_ticker_counts(normalized_tc)}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--submission",
        type=str,
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
    args = parser.parse_args()
    
    logging.basicConfig(
        filename="wsb_scraper.log",
        level=logging.INFO
    )

    reddit = praw.Reddit(
        client_id="Q0GxKcurTVudUQ",
        client_secret="gNij1LOfLX-gfUF_al-XTk-JU0ADFQ",
        user_agent="jesuspwndu",
        #username="my username",
        #password="my password"
    )
    wsb = reddit.subreddit("wallstreetbets")


    submission = reddit.submission(id=args.submission)
    res = scrape_submission(
        submission,
        comment_expansion_limit=32
    )
    logging.info(f"Writing submission results to {args.output}")
    write_submission_result(args.output, res)

if __name__ == "__main__":
    main()

