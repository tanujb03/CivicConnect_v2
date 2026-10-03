# Native-speaker review of LLM-written Indic text

**Why:** the gold set `ai/training/gold/gold_llm_authored_claude_v1.csv` was written by an LLM (provenance `llm_authored_claude`, a different model family from the Gemini/Groq
corpus generators). LLM-written Hindi and Marathi can sound translated, stiff or regionally off, and the same applies to the training corpus. Until a native speaker has signed off,
no accuracy number computed on these rows may be called a real-world result. The 20 lines per language below are a seeded random sample (`random.Random(seed)`, seed 7 for Hindi and 11 for Marathi, drawn from the 84 lines of each language);
if the sample shows problems, review all 84 lines of that language in the CSV (rows are numbered below as `row N` = N-th data row after the header).

## How to review (one tick per line)

1. **Natural?** Would a real citizen write or say this? Fix stiff, over-formal or word-for-word-translated phrasing.
2. **Right register for its style tag** (`sms`, `angry`, `polite`, `plain`, `landmark`, `typo`, `mixed`): terse for SMS, no polite forms in `angry`, spelling slips only in `typo`.
3. **Correct language:** Hindi vs Marathi grammar and vocabulary (not Hindi words in Marathi dress, or the reverse); correct script and spelling outside `typo` rows.
4. **Label still fits:** the text clearly belongs to the stated `label_id` and to no other label.
5. **Safe:** no real person, phone number, address or offensive wording.

Mark `[x]` when the line is fine as written. If it needs a change, leave `[ ]` and write the corrected text after `fix:`. Record reviewer name and date at the end of each section.

## Hindi (hi): sample of 20 (of 84)

- [ ] row 89 · `roads/pothole` · typo: पेट्रोल पम्प के पास सडक पर गडढा बारिश के बाद रोज बडा होता जा रहा हे  
  fix: 
- [ ] row 91 · `roads/road_cave_in` · plain: नाले के किनारे वाली सड़क अचानक धँस गई, करीब चार फुट गहरा गड्ढा बन गया है और ऊपर से सड़क खोखली लग रही है।  
  fix: 
- [ ] row 92 · `roads/road_cave_in` · angry: हमारी गली के बीच में सड़क बैठ गई है और एक ऑटो का पहिया अंदर चला गया। जब कोई मरेगा तब आओगे क्या?  
  fix: 
- [ ] row 93 · `roads/road_cave_in` · landmark: पानी की टंकी के पास सड़क करीब डेढ़ फुट नीचे बैठ गई है और दरार हर दिन बढ़ती जा रही है।  
  fix: 
- [ ] row 94 · `drainage_sewerage/blocked_drain` · plain: हमारी गली की नाली प्लास्टिक और कचरे से जाम हो गई है, गंदा पानी सड़क पर फैल रहा है।  
  fix: 
- [ ] row 96 · `drainage_sewerage/blocked_drain` · polite: कृपया डाकघर के पीछे वाली नाली साफ करवा दें, पिछली बारिश से बंद पड़ी है और ज़रा-सी बारिश में पूरी गली डूब जाती है।  
  fix: 
- [ ] row 97 · `drainage_sewerage/missing_manhole_cover` · plain: मंदिर के पास वाली गली में मैनहोल का ढक्कन ग़ायब है, खुला गड्ढा बच्चों के लिए बहुत ख़तरनाक है।  
  fix: 
- [ ] row 104 · `parks_trees/damaged_park_equipment` · polite: क्या कॉलोनी पार्क की फिसलपट्टी की मरम्मत हो सकती है? उसका नुकीला लोहा बाहर आ गया है, किसी बच्चे को चोट लग सकती है।  
  fix: 
- [ ] row 112 · `public_health/mosquito_breeding` · plain: हमारी बिल्डिंग के पीछे वाले ख़ाली प्लॉट में गंदा पानी भरा है और उसमें मच्छर पनप रहे हैं।  
  fix: 
- [ ] row 115 · `public_health/open_burning` · plain: रोज़ शाम को कोई खुले मैदान में कचरा और प्लास्टिक जलाता है, धुआँ सीधे हमारे घरों में आता है।  
  fix: 
- [ ] row 126 · `sanitation/dead_animal` · polite: कल रात से हमारे गेट के बाहर फुटपाथ पर एक मरी बिल्ली पड़ी है, कृपया बदबू फैलने से पहले उठवा दें।  
  fix: 
- [ ] row 131 · `sanitation/illegal_dumping` · polite: कृपया झील वाली सड़क पर रात को ट्रक से कचरा गिराने वालों पर कार्रवाई करें, यह खुलेआम अवैध डंपिंग है।  
  fix: 
- [ ] row 135 · `sanitation/missed_garbage_collection` · angry: हमारी सोसायटी कचरा शुल्क देती है फिर भी गाड़ी हर दूसरे दिन छोड़ जाती है, अब पाँच दिन हो गए। यह नहीं चलेगा।  
  fix: 
- [ ] row 138 · `street_lighting/exposed_live_wire` · sms: स्कूल की दीवार के पास तार नीचे लटका है, करंट का डर  
  fix: 
- [ ] row 139 · `street_lighting/flickering_light` · plain: हमारी सड़क की स्ट्रीट लाइट रात भर बार-बार जलती-बुझती रहती है।  
  fix: 
- [ ] row 140 · `street_lighting/flickering_light` · sms: पार्क गेट के पास लाइट टिमटिमा रही है, लोग परेशान हैं  
  fix: 
- [ ] row 149 · `traffic_encroachment/illegal_parking` · sms: फिर मेरे गेट के आगे गाड़ी खड़ी है, नंबर प्लेट दिख रही है। उठवाइए  
  fix: 
- [ ] row 153 · `traffic_encroachment/signal_not_working` · sms: रिंग रोड चौराहे पर सिग्नल लाल पर अटका है, बदल नहीं रहा, लंबा जाम  
  fix: 
- [ ] row 155 · `water_supply/contaminated_water` · angry: तीन दिन से नलों में गंदा भूरा पानी आ रहा है और बच्चे बीमार पड़ रहे हैं। हम टैक्स किस बात का भरते हैं?  
  fix: 
- [ ] row 159 · `water_supply/low_water_pressure` · polite: कृपया हमारी लाइन का प्रेशर जाँच लें, पिछले दो हफ्ते से शाम को नल से सिर्फ़ बूँद-बूँद पानी आता है।  
  fix: 

Reviewer: ____________ · Date: ____________ · Lines needing a fix: ___ / 20

## Marathi (mr): sample of 20 (of 84)

- [ ] row 174 · `roads/pothole` · mixed: साहेब इथे रस्त्यावर खूप मोठा pothole आहे signal जवळ, अपघात होऊ शकतो  
  fix: 
- [ ] row 180 · `drainage_sewerage/blocked_drain` · polite: कृपया पोस्ट ऑफिसमागचं गटार साफ करून द्यावं, गेल्या पावसापासून बंद आहे आणि थोड्या पावसातही संपूर्ण गल्लीत पाणी भरतं.  
  fix: 
- [ ] row 181 · `drainage_sewerage/missing_manhole_cover` · plain: मंदिराजवळच्या गल्लीत मॅनहोलचं झाकण नाही, उघडा खड्डा लहान मुलांसाठी खूप धोकादायक आहे.  
  fix: 
- [ ] row 187 · `parks_trees/damaged_park_equipment` · plain: लहान मुलांच्या बागेतला झोका तुटला आहे आणि त्याची साखळी लोंबकळते आहे, तरीही मुलं त्यावर बसतात.  
  fix: 
- [ ] row 189 · `parks_trees/damaged_park_equipment` · sms: वॉर्ड ६ च्या बागेत सी-सॉ तुटला आहे, दुरुस्त करा  
  fix: 
- [ ] row 192 · `parks_trees/fallen_tree` · angry: बस निवाऱ्यावर वादळापासून एक जड फांदी लटकते आहे, अजून कोणी तोडली का नाही? कोणाचा जीव गेल्यावर तोडणार का?  
  fix: 
- [ ] row 193 · `parks_trees/overgrown_vegetation` · plain: वसाहतीच्या बागेत गवत आणि झुडपं कमरेपर्यंत वाढली आहेत, आत साप दिसले आहेत.  
  fix: 
- [ ] row 207 · `roads/damaged_footpath` · typo: दवाखान्याच्या गेटजवळ पदपथाच्या फरश्या तुटल्यात, व्हीलचेअर जाऊ शकत नाही  
  fix: 
- [ ] row 219 · `sanitation/missed_garbage_collection` · angry: आमची सोसायटी कचरा शुल्क भरते तरीही गाडी दर दुसऱ्या दिवशी चुकवते, आता पाच दिवस झाले. हे चालणार नाही.  
  fix: 
- [ ] row 226 · `street_lighting/light_not_working` · plain: आमच्या गल्लीतले पथदिवे आठवडाभर बंद आहेत आणि रात्री पूर्ण अंधार असतो.  
  fix: 
- [ ] row 228 · `street_lighting/light_not_working` · landmark: उड्डाणपुलाच्या रॅम्पवर मेट्रोच्या खांबाजवळचे सगळे दिवे बंद आहेत, दुचाकीस्वारांना खड्डे दिसतच नाहीत.  
  fix: 
- [ ] row 229 · `traffic_encroachment/footpath_encroachment` · plain: स्टेशनबाहेर संपूर्ण पदपथावर फेरीवाल्यांनी कब्जा केला आहे, लोकांना रस्त्यावरून चालावं लागतं.  
  fix: 
- [ ] row 234 · `traffic_encroachment/illegal_parking` · angry: दररोज संध्याकाळी मॉलसमोर झेब्रा क्रॉसिंगवर गाड्या उभ्या असतात आणि पादचारी रस्ता ओलांडू शकत नाहीत. वाहतूक पोलीस कुठे आहेत?  
  fix: 
- [ ] row 240 · `water_supply/contaminated_water` · typo: नळाच्या पाण्यात अळ्या निघताहेत, उकळूनही वापरता येत नाही  
  fix: 
- [ ] row 244 · `water_supply/no_water_supply` · plain: काल सकाळपासून आमच्या वस्तीत पाणीपुरवठा पूर्णपणे बंद आहे.  
  fix: 
- [ ] row 245 · `water_supply/no_water_supply` · angry: तीन दिवस आमच्या गल्लीत पाणी आलं नाही!! टँकरवाले मनमानी भाव लावतात. पुरवठा आत्ताच सुरू करा.  
  fix: 
- [ ] row 248 · `water_supply/pipe_leakage` · landmark: मंदिर चौकाजवळ पाण्याची मुख्य पाइपलाइन फुटली आहे, रस्त्यावर खूप पाणी वाहत आहे.  
  fix: 
- [ ] row 249 · `water_supply/pipe_leakage` · sms: गल्ली ५ च्या कोपऱ्यावर पाइप गळतोय, रात्रभर पाणी वाया गेलं  
  fix: 
- [ ] row 251 · `other/unclassified` · polite: नवीन गृहसंकुलाजवळ बस थांबा करता येईल का? सर्वात जवळचा थांबा एक किलोमीटरपेक्षा जास्त दूर आहे.  
  fix: 
- [ ] row 252 · `other/unclassified` · sms: आमच्या वॉर्डातलं समाज वाचनालय महिनोन्महिने बंद आहे, कृपया पाहा  
  fix: 

Reviewer: ____________ · Date: ____________ · Lines needing a fix: ___ / 20

## After review

- Apply the fixes to the CSV (keep provenance `llm_authored_claude`; if a reviewer rewrites a line, that line is then human-edited: move it to a separate file, never mix it into the LLM-authored one).
- If more than 4 of 20 lines in a language needed a fix, review all 84 lines of that language before using them for evaluation.
- After editing the CSV, re-validate it with the repo loader (`ai.training.src.text_corpus.build.load_gold`): it must still accept every row.
