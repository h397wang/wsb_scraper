from wsb_scraper import *
import unittest
import praw

def set_equal(a, b):
    return len(a - b) == 0


def set_empty(a):
    return len(a) == 0



class TestTickerMethods(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestTickerMethods, self).__init__(*args, **kwargs)
        self.reddit = praw.Reddit(
            client_id="Q0GxKcurTVudUQ",
            client_secret="gNij1LOfLX-gfUF_al-XTk-JU0ADFQ",
            user_agent="jesuspwndu",
        )
        self.wsb = self.reddit.subreddit("wallstreetbets")


    def setUp(self):
        pass

    def test_word_is_ticker(self):
        self.assertTrue(word_is_ticker("TSLA"))
        self.assertTrue(word_is_ticker("NET"))
        self.assertTrue(word_is_ticker("$PLTR"))

        self.assertFalse(word_is_ticker("a"))
        self.assertFalse(word_is_ticker("i"))
        self.assertFalse(word_is_ticker("ummm"))
        self.assertFalse(word_is_ticker("Apple"))
        self.assertFalse(word_is_ticker("REEEEEE"))
        self.assertFalse(word_is_ticker("FUCK"))

    def test_extract_tickers_from_text(self):
        expected = {"PLTR", "NET", "TESLA"}
        t = extract_tickers_from_text("PLTR, NET, TESLA")
        self.assertTrue(set_equal(expected, t))

        t = extract_tickers_from_text("PLTR NET TESLA")
        self.assertTrue(set_equal(expected, t))
        
        t = extract_tickers_from_text("PLTR,NET,TESLA")
        self.assertTrue(set_equal(expected, t))
        
        t = extract_tickers_from_text("PLTR to the moon")
        self.assertTrue(set_equal({"PLTR"}, t))

        t = extract_tickers_from_text("stonks only go up")
        self.assertTrue(set_empty(t))

    def test_normalize_ticker(self):
        t = normalize_ticker("PLTR")
        self.assertEqual("PLTR", t)

        t = normalize_ticker("$PLTR")
        self.assertEqual("PLTR", t)

    def test_merge_word_counts(self):
        a = {
            "1" : 1,
            "2" : 2,
            "3" : 3,
        }
        b = {
            "1" : 1,
            "2" : 2,
        }
        merge_word_counts(a, b)
        self.assertEqual(a["1"], 2)
        self.assertEqual(a["2"], 4)
        self.assertEqual(a["3"], 3)

    def test_set_to_count(self):
        s = {"PLTR", "TSLA"}
        d = set_to_count(s)
        for k in d:
            self.assertEqual(d[k], 1)

    def test_scrape_submission(self):
        #submission = reddit.submission(id="k29omq")
        #ret = scrape_submission(submission)
        pass

if __name__ == "__main__":
    unittest.main()      