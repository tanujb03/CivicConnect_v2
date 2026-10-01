"""Shared (label-independent) surface material: places, frames, noise inputs.

Frames/prefixes/suffixes are NOT part of a template family and appear in every
split; only the core issue phrase (the family) and the place names are held out.
"""
# (latin, devanagari, tags)
PLACES = [
    ("Shivaji Nagar", "शिवाजी नगर", []), ("Gandhi Chowk", "गांधी चौक", []), ("Sai Colony", "साई कॉलोनी", []),
    ("Station Road", "स्टेशन रोड", ["transit_stop"]), ("Laxmi Market", "लक्ष्मी मार्केट", ["market"]),
    ("Ambedkar School", "आंबेडकर स्कूल", ["school"]), ("City Hospital", "सिटी हॉस्पिटल", ["hospital"]),
    ("Nehru Park", "नेहरू पार्क", []), ("Rose Garden Society", "रोज़ गार्डन सोसायटी", []),
    ("Tilak Road", "टिळक रोड", []), ("Bus Depot", "बस डिपो", ["transit_stop"]),
    ("Krishna Heights", "कृष्णा हाइट्स", []), ("Mahatma Phule School", "महात्मा फुले स्कूल", ["school"]),
    ("Green Valley Hospital", "ग्रीन वैली हॉस्पिटल", ["hospital"]), ("Old Bazaar", "ओल्ड बाज़ार", ["market"]),
    ("Sunrise Apartments", "सनराइज अपार्टमेंट", []), ("Ram Mandir Lane", "राम मंदिर लेन", []),
    ("Bhagat Singh Chowk", "भगत सिंह चौक", []), ("Lake View Colony", "लेक व्यू कॉलोनी", []),
    ("Ward Office Road", "वॉर्ड ऑफिस रोड", []),
]

CITY_CENTER = (19.0760, 72.8777)  # synthetic city; coordinates are fictional placements

PLACE_CLAUSES = {
    "en": ["near {p}", "at {p}", "opposite {p}", "in front of {p}"],
    "hi": ["{p} के पास", "{p} पर", "{p} के सामने"],
    "mr": ["{p} जवळ", "{p} येथे", "{p} समोर"],
    "hl": ["{p} ke paas", "{p} par", "{p} ke saamne"],
}
PREFIXES = {
    "en": ["Hello,", "Sir,", "Kindly note:", "Urgent!", "Complaint:", "Please help."],
    "hi": ["नमस्कार,", "सर,", "कृपया ध्यान दें:", "शिकायत:", "अर्जेंट!", "Complaint:"],
    "mr": ["नमस्कार,", "साहेब,", "कृपया लक्ष द्या:", "तक्रार:", "तातडीने!", "Complaint:"],
    "hl": ["Sir,", "Namaste,", "Kripya dhyan dein:", "Complaint:", "Urgent!", "Bhaiya,"],
}
SUFFIXES = {
    "en": ["Please fix it soon.", "Kindly take action.", "It has been like this for {n} days.", "Thank you.", "Nobody is responding."],
    "hi": ["कृपया जल्दी ठीक करें।", "कार्रवाई करें।", "यह {n} दिन से ऐसा ही है।", "धन्यवाद।", "कोई सुन नहीं रहा।"],
    "mr": ["कृपया लवकर दुरुस्त करा.", "कारवाई करा.", "हे {n} दिवसांपासून असेच आहे.", "धन्यवाद.", "कोणी लक्ष देत नाही."],
    "hl": ["Please jaldi theek karein.", "Action lijiye.", "Yeh {n} din se aisa hi hai.", "Thank you.", "Koi sun nahi raha."],
}
# English sprinkled into en text to simulate Indian-English/Hinglish code-mixing
EN_CODEMIX_SUFFIX = ["Kindly do the needful, jaldi karein.", "Please action lijiye.", "Yeh problem bahut din se hai."]

LANGS = ("en", "hi", "mr", "hl")
LANG_TAG = {"en": "en", "hi": "hi", "mr": "mr", "hl": "hi-Latn"}
N_FAMILIES = 5
