"""
ml/import_parser/training_data.py
────────────────────────────────────
Reference column-name examples for Smart Import's Stage 2 embedding matcher
(ml/import_parser/parser.py). Each canonical field maps to 50+ synthetic
header strings a real spreadsheet might use, covering:

  - Standard English names
  - German names (a large share of the trackers this feature targets are
    for the German job market — Werkstudent/Praktikum applications)
  - Abbreviations
  - Typos
  - Creative / conversational names
  - Emoji-prefixed names

At import time, every detected column header is embedded and compared
against every example below (best match wins) — the size and diversity of
this list is what lets the matcher generalize to headers it has never seen,
rather than requiring an exact or near-exact string match like the old
rule-based fuzzy matcher did.

Keep list values lowercase-friendly free text — they're embedded as-is,
punctuation and casing barely matter to the sentence embedding model.
"""

TRAINING_DATA: dict[str, list[str]] = {
    "job_title": [
        # Standard English
        "job title", "title", "position", "role", "job", "position title",
        "job role", "job position", "role title", "vacancy", "designation",
        "job name", "position name", "opening", "job opening",
        "role applied for", "position applied for", "the job", "job applied for",
        "role name", "job description", "posting title", "listing title",
        # German
        "stelle", "stellenbezeichnung", "berufsbezeichnung", "position (de)",
        "praktikum", "werkstudent", "ausschreibung", "jobtitel", "stellentitel",
        "tätigkeit",
        # Abbreviations
        "pos", "jt", "job ttl", "role/pos", "job/role", "pos.", "ttl",
        # Typos
        "jobtile", "postion", "titel", "rol", "jobtitel2", "psition",
        "job titel", "roll", "titile", "posiiton",
        # Creative / conversational
        "what i applied for", "the role", "what role", "applying for",
        "role i want", "dream job", "job i applied to", "what job",
        "position i want", "the gig", "the opportunity", "opportunity",
        "role/internship", "internship title", "programme", "program applied for",
        # Emoji-prefixed
        "💼 job title", "🧑‍💼 role", "📌 position", "🎯 role applied for",
        "💼 role", "📋 job title", "🏷️ position",
    ],
    "company": [
        # Standard English
        "company", "employer", "organisation", "organization", "company name",
        "hiring company", "firm", "employer name", "business", "org",
        "recruiter", "recruiting firm", "hiring organization", "corp",
        "corporation", "workplace", "hiring manager company",
        # German
        "unternehmen", "arbeitgeber", "firma", "firmenname", "gesellschaft",
        "arbeitgeber (de)", "unternehmensname",
        # Abbreviations
        "co", "co.", "cmpny", "empl", "org.", "corp.",
        # Typos
        "compnay", "compny", "companyy", "emplyer", "compamy", "cmpany",
        "orgnization", "firmm",
        # Creative
        "where i applied", "the place", "who i'm applying to", "employer i want",
        "target company", "dream company", "who's hiring", "the business",
        "which company", "applying to (company)", "where", "company i applied to",
        # Emoji-prefixed
        "🏢 company", "🏢 employer", "🏭 organisation", "🏢 firm", "🏫 company name",
        "🏢 unternehmen",
    ],
    "location": [
        # Standard English
        "location", "city", "place", "region", "office", "job location",
        "work location", "site", "office location", "area", "country",
        "city/region", "based in", "workplace location", "geo",
        # German
        "standort", "ort", "arbeitsort", "stadt", "einsatzort", "region (de)",
        "dienstort",
        # Abbreviations
        "loc", "loc.", "city/state", "addr", "location(s)",
        # Typos
        "locaton", "locatoin", "citty", "regoin", "locaiton",
        # Creative
        "where it is", "where based", "the place (city)", "based where",
        "where's the job", "office city", "onsite location", "site/remote",
        "which city", "geo location", "job city", "where you'd work",
        # Emoji-prefixed
        "📍 location", "🌍 location", "🏙️ city", "📍 office", "🗺️ region",
        "📍 standort",
    ],
    "date_applied": [
        # Standard English
        "date applied", "applied on", "application date", "date", "sent",
        "date sent", "applied date", "submission date", "apply date",
        "date submitted", "when applied", "date of application",
        "application submitted", "date of applying", "submitted on",
        # German
        "datum", "bewerbungsdatum", "beworben am", "datum der bewerbung",
        "angewendet am", "sendedatum",
        # Abbreviations
        "app date", "dt applied", "date appl.", "sub date", "d.o.a.",
        # Typos
        "date aplied", "aplication date", "dat applied", "dateapplied",
        "submited date",
        # Creative
        "when i sent it", "when i applied", "where i sent it", "sent when",
        "date i applied", "day applied", "when submitted", "application day",
        "when i hit submit", "sent it on", "application timing", "when did i apply",
        # Emoji-prefixed
        "📅 date applied", "🗓️ applied on", "📆 date", "⏰ application date",
        "📅 datum", "🗓️ sent",
        "application submitted on", "when it was sent",
    ],
    "status": [
        # Standard English
        "status", "application status", "stage", "state", "result", "outcome",
        "progress", "current status", "app status", "pipeline stage",
        "where it stands", "current stage",
        # German
        "stand", "bewerbungsstatus", "status (de)", "stand der bewerbung",
        "aktueller stand",
        # Abbreviations
        "stat", "stat.", "sts", "app stat",
        # Typos
        "stauts", "statuss", "staus", "statuts", "satus",
        # Creative
        "how it's going", "where things stand", "progress so far",
        "what happened", "the outcome", "current state", "update",
        "latest update", "how far", "where at", "what's next", "current phase",
        # Emoji-prefixed
        "✅ status", "📊 status", "🔄 stage", "📈 progress", "🚦 status",
        "🟢 status", "❓ status",
        "application stage", "tracking status", "where things are",
        "pipeline status", "process status",
    ],
    "job_url": [
        # Standard English
        "job url", "url", "link", "job link", "career page", "apply link",
        "website", "posting url", "listing url", "job posting", "posting link",
        "application link", "job page", "career site", "listing", "web link",
        "job website",
        # German
        "webseite", "bewerbungslink", "stellenlink", "link zur stelle",
        # Abbreviations
        "lnk", "url link", "href", "web addr",
        # Typos
        "jobb url", "ulr", "link ", "jon link", "linkk",
        # Creative
        "where to apply", "the link", "job posting link", "career page link",
        "click here", "job ad link", "vacancy link", "posting page",
        "the ad", "job ad", "where it's posted",
        # Emoji-prefixed
        "🔗 link", "🌐 url", "🔗 job link", "💻 apply link", "🔗 career page",
        "🔗 webseite",
        "careers page link", "application url", "job advert link",
    ],
    "notes": [
        # Standard English
        "notes", "comments", "remarks", "memo", "additional notes",
        "extra notes", "details", "comment", "note", "feedback",
        "personal notes", "observations", "follow up notes", "misc",
        # German
        "notizen", "anmerkungen", "bemerkungen", "kommentare", "hinweise",
        # Abbreviations
        "cmt", "cmts", "nts", "rmks",
        # Typos
        "notess", "commetns", "remaks", "noets", "coments",
        # Creative
        "my thoughts", "what i think", "extra info", "context",
        "why applied", "reasoning", "backstory", "additional info",
        "anything else", "side notes", "free text", "notes to self",
        # Emoji-prefixed
        "📝 notes", "💬 comments", "🗒️ notes", "✏️ remarks", "📝 notizen",
        "💭 thoughts",
        "my notes", "internal notes", "personal comments", "log entry",
    ],
    "salary": [
        # Standard English
        "salary", "compensation", "pay", "salary range", "expected salary",
        "comp", "wage", "annual salary", "base salary", "pay range",
        "salary expectation", "offered salary", "package", "total comp",
        "compensation range",
        # German
        "gehalt", "vergütung", "gehaltsvorstellung", "lohn", "bezahlung",
        "jahresgehalt",
        # Abbreviations
        "sal", "sal.", "comp.", "€/yr", "salary (k)",
        # Typos
        "salery", "salay", "compensaton", "salray", "wagee",
        # Creative
        "how much", "money", "what it pays", "the pay", "pay expectation",
        "target salary", "asking salary", "expected pay", "what they'll pay",
        "comp details",
        # Emoji-prefixed
        "💰 salary", "💵 compensation", "💶 gehalt", "💰 pay range", "💵 comp",
        "💰 wage",
        "pay details", "remuneration", "comp expectation",
    ],
    "platform": [
        # Standard English
        "platform", "source", "portal", "channel", "board", "via",
        "job board", "found via", "applied via", "application source",
        "job portal", "referral source", "how found", "found on",
        "sourced from",
        # German
        "quelle", "plattform", "jobbörse", "gefunden über", "kanal",
        # Abbreviations
        "src", "plat.", "chnl",
        # Typos
        "platfrom", "plateform", "sourse", "portall", "channell",
        # Creative
        "where i found it", "how i heard", "where from", "discovered via",
        "found through", "came from", "referral", "who told me",
        "heard about it from", "job site used", "application channel",
        "how i applied", "where posted",
        # Emoji-prefixed
        "🔍 source", "📱 platform", "🌐 job board", "📣 found via", "🔗 portal",
        "📲 channel", "🔍 quelle",
        "application platform", "job search platform",
    ],
}
