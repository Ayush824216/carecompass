// Demo inputs (data, not UI copy): the same text in both UI languages.
export const CARE_EXAMPLES = [
  { key: "hinglish", text: "Papa ko do din se bukhar hai aur khansi bhi" },
  { key: "hindi", text: "मम्मी को तीन महीने से घुटनों में दर्द है, सीढ़ी चढ़ने में दिक्कत होती है" },
  { key: "english", text: "I have had a runny nose and sneezing since yesterday" },
  { key: "nurse", text: "My mother needs the injections the doctor advised, given at home every day" },
  { key: "emergency", text: "Dadaji ke seene mein tez dard ho raha hai aur paseena aa raha hai" },
];

export const DEV_PRESETS = [
  { key: "hinglish", user_input: "Papa ko do din se bukhar hai aur khansi bhi", language: "auto" },
  { key: "hindi", user_input: "मुझे दो दिन से बुखार है, बदन दर्द है, बाकी सब ठीक है", language: "auto" },
  { key: "english", user_input: "I keep sneezing and my nose is blocked, started today", language: "auto" },
  { key: "nurse", user_input: "My father needs daily insulin injections at home, he cannot do it himself", language: "auto" },
  { key: "specialist", user_input: "Mummy ko 6 mahine se ghutno mein dard hai, seedhi chadhne mein dikkat", language: "auto" },
  { key: "emergency", user_input: "He suddenly can't lift his right arm and his words are jumbled", language: "auto" },
  { key: "negation", user_input: "Seene mein dard nahi hai, saans ki dikkat bhi nahi, bas gas aur acidity hai", language: "auto" },
];
