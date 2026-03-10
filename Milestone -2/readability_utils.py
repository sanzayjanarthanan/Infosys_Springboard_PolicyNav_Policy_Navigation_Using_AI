# readability_utils.py
# readability_utils.py
import textstat

class ReadabilityAnalyzer:
    def __init__(self, text):
        self.text = text
        self.num_sentences = max(1, text.count("."))
        self.num_words = len(text.split())
        self.char_count = len(text)
        self.syllables = textstat.syllable_count(text)
        self.complex_words = textstat.lexicon_count(text, removepunct=True)

    def get_all_metrics(self):
        return {
            "Flesch Reading Ease": textstat.flesch_reading_ease(self.text),
            "Flesch-Kincaid Grade": textstat.flesch_kincaid_grade(self.text),
            "Gunning Fog": textstat.gunning_fog(self.text),
            "SMOG Index": textstat.smog_index(self.text),
            "Coleman-Liau": textstat.coleman_liau_index(self.text)
        }
