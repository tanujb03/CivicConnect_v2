"""Hand-written synthetic issue phrases (one *template family* per phrase).

SYNTHETIC DATA: all phrases are invented for model development. Hindi/Marathi
text requires native-speaker review. ``FAMILIES[subcategory][language]`` is a list
of exactly 5 core phrases; the family index (0-4) drives the held-out split.
Languages: en, hi (Devanagari), mr (Devanagari), hl (romanised Hinglish).
Hindi/Marathi review status: the repository owner (a Hindi/Marathi speaker) read the phrases on 2026-10-02 and cross-checked them with a second tool; nine
wording corrections were applied. This is an informal review, NOT an independent professional/native-speaker audit.
"""
FAMILIES: dict[str, dict[str, list[str]]] = {}

FAMILIES["pothole"] = {
 "en": ["there is a big pothole in the road", "a deep hole has formed on the road surface and bikes are skidding",
        "the road is full of potholes after the rain", "huge crater in the middle of the lane, cars swerve to avoid it",
        "tarmac has broken and left a dangerous pit"],
 "hi": ["सड़क पर बड़ा गड्ढा हो गया है", "सड़क में गहरा गड्ढा है और बाइक फिसल रही हैं",
        "बारिश के बाद पूरी सड़क गड्ढों से भर गई है", "सड़क के बीच में बहुत बड़ा गड्ढा है, गाड़ियाँ उसे बचाकर निकलती हैं",
        "डामर उखड़ गया है और खतरनाक गड्ढा बन गया है"],
 "mr": ["रस्त्यावर मोठा खड्डा पडला आहे", "रस्त्यात खोल खड्डा आहे आणि दुचाकी घसरत आहेत",
        "पावसानंतर संपूर्ण रस्ता खड्ड्यांनी भरला आहे", "रस्त्याच्या मधोमध मोठा खड्डा आहे, गाड्या चुकवून जातात",
        "डांबर उखडले असून धोकादायक खड्डा तयार झाला आहे"],
 "hl": ["sadak par bada gadda ho gaya hai", "road mein gehra gadda hai aur bikes slip ho rahi hain",
        "barish ke baad poori sadak gaddon se bhar gayi hai", "road ke beech mein bahut bada gadda hai, gaadiyan bachke nikalti hain",
        "tarkol ukhad gaya hai aur khatarnak gadda ban gaya hai"],
}
FAMILIES["road_cave_in"] = {
 "en": ["the road has caved in and a sinkhole has opened", "part of the road suddenly collapsed into the ground",
        "road surface is sinking near the pipeline and cracking badly", "a large depression has appeared and the road is giving way",
        "the street has subsided and traffic cannot pass safely"],
 "hi": ["सड़क धँस गई है और बड़ा सिंकहोल बन गया है", "सड़क का एक हिस्सा अचानक जमीन में बैठ गया",
        "पाइपलाइन के पास सड़क धँस रही है और बुरी तरह फट गई है", "बड़ा धँसाव हुआ है और सड़क धँस रही है",
        "गली की सड़क नीचे बैठ गई है, गाड़ियाँ सुरक्षित नहीं निकल सकतीं"],
 "mr": ["रस्ता खचला असून मोठा सिंकहोल तयार झाला आहे", "रस्त्याचा काही भाग अचानक जमिनीत खचला",
        "पाईपलाईनजवळ रस्ता खचत आहे आणि खूप तडे गेले आहेत", "मोठा धसाव झाला असून रस्ता खचत आहे",
        "गल्लीतील रस्ता खाली बसला आहे, वाहने सुरक्षित जाऊ शकत नाहीत"],
 "hl": ["sadak dhans gayi hai aur bada sinkhole ban gaya hai", "road ka ek hissa achanak zameen mein baith gaya",
        "pipeline ke paas sadak dhans rahi hai aur buri tarah phat gayi hai", "bada gaddha baith gaya hai aur road dab rahi hai",
        "gali ki road neeche baith gayi hai, gaadiyan safely nahi nikal sakti"],
}
FAMILIES["damaged_footpath"] = {
 "en": ["the footpath tiles are broken and uneven", "pavement is damaged and people with walking sticks keep tripping",
        "footpath slab has cracked and is sticking out", "the walkway beside the road is completely broken",
        "paving stones are missing from the sidewalk"],
 "hi": ["फुटपाथ की टाइलें टूटी हुई और ऊबड़-खाबड़ हैं", "फुटपाथ खराब है और बुजुर्ग लोग ठोकर खाकर गिरते हैं",
        "फुटपाथ का स्लैब टूटकर बाहर निकला हुआ है", "सड़क किनारे का पैदल रास्ता पूरी तरह टूट गया है",
        "फुटपाथ से पेवर ब्लॉक गायब हैं"],
 "mr": ["पदपथाच्या फरशा तुटलेल्या आणि असमान आहेत", "पदपथ खराब असून वृद्ध लोक अडखळून पडतात",
        "पदपथाचा स्लॅब तडकून बाहेर आला आहे", "रस्त्यालगतचा फुटपाथ पूर्णपणे तुटला आहे",
        "पदपथावरील पेव्हर ब्लॉक गायब आहेत"],
 "hl": ["footpath ki tiles tooti hui aur uneven hain", "footpath kharab hai aur buzurg log thokar khakar gir jaate hain",
        "footpath ka slab tootkar bahar nikla hua hai", "road ke kinare ka walkway poora toot gaya hai",
        "footpath se paver blocks gayab hain"],
}
FAMILIES["pipe_leakage"] = {
 "en": ["a water pipe is leaking and water is flowing on the road", "the main pipeline burst and clean water is wasting",
        "there is a continuous water leak from the underground pipe", "water is gushing out of a broken pipe joint",
        "pipe leakage has been flooding the lane since morning"],
 "hi": ["पानी की पाइप लीक हो रही है और सड़क पर पानी बह रहा है", "मुख्य पाइपलाइन फट गई है और साफ पानी बर्बाद हो रहा है",
        "जमीन के नीचे की पाइप से लगातार पानी रिस रहा है", "टूटे पाइप के जोड़ से पानी फव्वारे की तरह निकल रहा है",
        "सुबह से पाइप लीकेज से गली में पानी भर रहा है"],
 "mr": ["पाण्याची पाईप गळत आहे आणि रस्त्यावर पाणी वाहत आहे", "मुख्य जलवाहिनी फुटली असून स्वच्छ पाणी वाया जात आहे",
        "जमिनीखालील पाईपमधून सतत पाणी झिरपत आहे", "तुटलेल्या पाईपच्या जोडातून पाणी फवाऱ्यासारखे उडत आहे",
        "सकाळपासून पाईप गळतीमुळे गल्लीत पाणी साचत आहे"],
 "hl": ["paani ki pipe leak ho rahi hai aur road par paani beh raha hai", "main pipeline phat gayi hai aur saaf paani barbaad ho raha hai",
        "zameen ke neeche ki pipe se lagatar paani reesh raha hai", "toote pipe ke joint se paani fawwaare ki tarah nikal raha hai",
        "subah se pipe leakage se gali mein paani bhar raha hai"],
}
FAMILIES["no_water_supply"] = {
 "en": ["we have not received any water supply today", "no water is coming in the taps for three days",
        "the tap water supply has completely stopped in our area", "taps are dry since morning and there is no tanker either",
        "water supply has been cut off without any notice"],
 "hi": ["आज हमारे यहाँ पानी की सप्लाई नहीं आई", "तीन दिन से नलों में पानी नहीं आ रहा है",
        "हमारे इलाके में नल का पानी पूरी तरह बंद है", "सुबह से नल सूखे हैं और टैंकर भी नहीं आया",
        "बिना किसी सूचना के पानी की आपूर्ति बंद कर दी गई है"],
 "mr": ["आज आमच्याकडे पाणीपुरवठा झाला नाही", "तीन दिवसांपासून नळाला पाणी येत नाही",
        "आमच्या परिसरात नळाचे पाणी पूर्णपणे बंद आहे", "सकाळपासून नळ कोरडे आहेत आणि टँकरही आला नाही",
        "कोणतीही सूचना न देता पाणीपुरवठा बंद केला आहे"],
 "hl": ["aaj hamare yahan paani ki supply nahi aayi", "teen din se nalon mein paani nahi aa raha hai",
        "hamare area mein nal ka paani poori tarah band hai", "subah se nal sukhe hain aur tanker bhi nahi aaya",
        "bina kisi soochna ke paani ki supply band kar di gayi hai"],
}
FAMILIES["contaminated_water"] = {
 "en": ["the tap water is dirty and smells bad", "drinking water is coming brown and muddy",
        "supplied water has worms and people are falling sick", "tap water looks yellow and tastes foul",
        "the water supply is contaminated with sewage"],
 "hi": ["नल का पानी गंदा है और बदबू आ रही है", "पीने का पानी भूरा और मटमैला आ रहा है",
        "सप्लाई के पानी में कीड़े हैं और लोग बीमार पड़ रहे हैं", "नल का पानी पीला दिखता है और स्वाद खराब है",
        "पानी की सप्लाई में सीवर का पानी मिल गया है"],
 "mr": ["नळाचे पाणी गढूळ असून दुर्गंधी येत आहे", "पिण्याचे पाणी तपकिरी आणि चिखलयुक्त येत आहे",
        "पुरवठ्याच्या पाण्यात किडे आहेत आणि लोक आजारी पडत आहेत", "नळाचे पाणी पिवळसर दिसते आणि चव खराब आहे",
        "पाणीपुरवठ्यात सांडपाणी मिसळले आहे"],
 "hl": ["nal ka paani ganda hai aur badbu aa rahi hai", "peene ka paani brown aur matmaila aa raha hai",
        "supply ke paani mein keede hain aur log beemar pad rahe hain", "nal ka paani peela dikhta hai aur swaad kharab hai",
        "paani ki supply mein sewer ka paani mil gaya hai"],
}
FAMILIES["low_water_pressure"] = {
 "en": ["water pressure is very low and it barely reaches the first floor", "the tap flow is just a thin trickle",
        "pressure is too weak to fill the overhead tank", "water comes very slowly in the morning supply",
        "low pressure supply, upper floors get nothing"],
 "hi": ["पानी का दबाव बहुत कम है और पहली मंजिल तक मुश्किल से पहुँचता है", "नल से सिर्फ पतली धार आती है",
        "दबाव इतना कम है कि छत की टंकी नहीं भरती", "सुबह की सप्लाई में पानी बहुत धीरे आता है",
        "कम दबाव की सप्लाई है, ऊपरी मंजिलों पर कुछ नहीं आता"],
 "mr": ["पाण्याचा दाब खूप कमी आहे आणि पहिल्या मजल्यापर्यंत कसाबसा पोहोचतो", "नळातून फक्त बारीक धार येते",
        "दाब इतका कमी आहे की गच्चीवरची टाकी भरत नाही", "सकाळच्या पुरवठ्यात पाणी खूप हळू येते",
        "कमी दाबाचा पुरवठा आहे, वरच्या मजल्यांना काहीच येत नाही"],
 "hl": ["paani ka pressure bahut kam hai aur pehli manzil tak mushkil se pahunchta hai", "nal se sirf patli dhaar aati hai",
        "pressure itna kam hai ki chhat ki tanki nahi bharti", "subah ki supply mein paani bahut dheere aata hai",
        "low pressure supply hai, upar ki manzilon par kuch nahi aata"],
}
