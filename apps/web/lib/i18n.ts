/**
 * Flat en/hi string table. No i18n library.
 * Language lives in the ?lang= URL param and localStorage; <html lang> is
 * kept in sync by the language toggle. Monetary figures are never part of
 * these strings — they are interpolated from API responses.
 */

export type Lang = "en" | "hi";

const en = {
  /* Common */
  app_name: "DHAAL",
  loading: "Loading…",
  error_title: "Something went wrong",
  retry: "Try again",
  back_home: "← Start over",
  fixture_banner: "Sample data · a fictional policy and bill. Calculations are live.",
  you_pay: "You pay",
  status_verified: "Verified",
  status_unverified: "Unverified",
  status_unknown: "Unknown",
  status_conflicting: "Conflicting",
  status_user_confirmed: "You confirmed",
  status_synthetic: "Synthetic",
  status_missing: "Not found",
  page_of: "page {page}",
  session_not_found: "This session no longer exists. It may have been deleted.",

  /* Screen 1 — Goal */
  s1_title: "What are you planning for?",
  s1_intro:
    "Dhaal works out what a planned hospital stay may cost you after insurance — and shows the policy clause behind every rupee.",
  s1_goal_procedure: "A hospital procedure",
  s1_goal_admission: "A planned hospital admission",
  s1_goal_checking: "Just checking my policy",
  s1_describe_label: "Or describe it in your own words",
  s1_describe_placeholder: "e.g. Gallbladder surgery next month / अगले महीने पित्ताशय का ऑपरेशन",
  s1_sample_label: "Use sample data",
  s1_sample_note:
    "A fictional policy (Suraksha Shield Health) and a sample hospital bill. No upload needed.",
  s1_upload_label: "Your policy PDF (text PDF only, max 10 MB)",
  s1_upload_hint: "Scanned documents cannot be read. You can still use sample data.",
  s1_start: "Start →",
  s1_starting: "Starting…",
  s1_choose_file: "Choose a PDF file",
  s1_file_required: "Choose a policy PDF, or turn on sample data.",
  s5_row_source: "Document source",
  /* Screen 1 — Policy identification */
  s1_policy_title: "Which policy will you claim under?",
  s1_policy_intro:
    "Every figure Dhaal shows must come from your policy's own wording. Find your exact policy below, or upload your policy PDF.",
  s1_mode_find: "Find my policy",
  s1_mode_upload: "Upload my policy PDF",
  s1_mode_sample: "Try the sample policy",
  s1_search_label: "Search by insurer or product name",
  s1_search_placeholder: "Start typing — e.g. Suraksha or AarogyaKavach",
  s1_search_hint:
    "Dhaal can only list policy wordings it actually holds and can verify. If yours is not listed, upload your policy PDF instead — never pick a look-alike policy.",
  s1_searching: "Searching…",
  s1_search_empty:
    "No policy we hold matches that. Check the spelling, or upload your policy PDF below.",
  s1_search_error: "Search didn't work. Check your connection and try again.",
  s1_version_label: "Which version is your policy? Check your policy schedule.",
  s1_effective_from: "wording effective {date}",
  s1_fictional_badge: "Fictional sample",
  s1_policy_selected: "Selected policy",
  s1_change_policy: "Change",
  s1_declared_insurer: "Insurer (from your policy schedule)",
  s1_declared_product: "Product name (from your policy schedule)",
  s1_declared_note:
    "Optional, but recommended. Dhaal reads the PDF you upload; it cannot verify it against an official wording, so check every clause on the next screen.",
  s1_need_selection: "Choose your exact policy and version above to continue.",
  s1_uin: "UIN {uin}",

  /* Screen 2 — Review conditions */
  s2_review_title: "Review your policy conditions",
  s2_review_intro:
    "These conditions were found in the wording. Only clauses shown here can change what you pay — check each one against the document text before continuing.",
  s2_policy_block_title: "Policy being simulated",
  s2_source_catalogue: "Held wording from the catalogue",
  s2_source_upload: "Your uploaded PDF — not verified against an official wording",
  s2_prov_version: "Version {version}",
  s2_prov_effective: "effective {date}",
  s2_prov_hash: "SHA-256 {hash}…",
  s2_declared_badge: "Name as you declared it",
  s2_plain_label: "In plain words",
  s2_conditions_label: "Applies to",
  expl_room_pct:
    "Room rent is paid only up to {pct} of your sum insured per day. Above that, the excess — and possibly a share of other charges — is yours to pay.",
  expl_room_fixed:
    "Room rent is paid only up to {amount} per day. Above that, the excess — and possibly a share of other charges — is yours to pay.",
  expl_apportionment:
    "If your room costs more than the limit, other charges may also be cut in proportion. Exactly which charges count is decided by this wording.",
  expl_initial: "Illnesses are not covered during the first {days} days of the policy{accident}.",
  expl_initial_accident: " (accidents are covered from day one)",
  expl_specified:
    "The diseases and procedures listed in this clause are covered only after {months} months of continuous cover.",
  expl_ped:
    "Pre-existing diseases are covered only after {months} months of continuous cover.",
  expl_exclusion: "These treatments are never covered under this policy.",
  expl_nonpayable:
    "The insurer will not pay for these items, even if the hospital bills them.",
  expl_copay: "You pay {pct} of every admissible claim amount yourself.",
  expl_deductible: "You pay the first {amount} of each claim yourself.",

  /* Screen 3 — Claim details */
  s3_claim_title: "About this claim",
  s3_claim_intro:
    "Waiting periods and exclusions depend on the treatment and on your policy history. Give the facts here — Dhaal will not guess them, and anything unsure stays visibly unresolved.",
  s3_condition_label: "Condition / procedure",
  s3_condition_unsure: "I'm not sure",
  s3_condition_other: "Something else (not listed)",
  s3_ped_label: "Is this treatment for a pre-existing condition?",
  s3_yes: "Yes",
  s3_no: "No",
  s3_unsure: "Not sure",
  s3_accident_label: "Is this admission due to an accident?",
  s3_inception_label: "Policy start date",
  s3_admission_label: "Admission date",
  s3_credit_label: "Months of earlier continuous cover credited (portability)",
  s3_dates_derived: "From these dates: {months} months ({days} days) of cover at admission.",
  s3_estimate_note:
    "This is an estimate worked out from the policy wording — not an insurer-approved settlement. The insurer assesses the actual claim on its own terms.",


  /* Consent */
  consent_title: "What happens to your information",
  consent_purpose_h: "Purpose",
  consent_purpose: "Work out your estimated out-of-pocket cost for this one hospital stay.",
  consent_docs_h: "Documents",
  consent_docs: "Your policy text is read to find the clauses that change what you pay.",
  consent_retention_h: "Retention",
  consent_retention: "Kept only for this session. Delete it any time from the “Your data” screen.",
  consent_dont_h: "What we don't do",
  consent_dont:
    "We don't sell insurance or loans, and we never say a claim will be approved. All figures are estimates from the wording you give us.",

  /* Screen 2 — Evidence */
  s2_title: "Your policy, clause by clause",
  s2_doc_meta: "{pages} pages",
  s2_unconfirmed: "{count} key fact(s) still need your decision before we can calculate.",
  s2_review: "Review",
  s2_group_coverage: "Coverage",
  s2_group_waiting: "Waiting periods",
  s2_group_limits: "Limits",
  s2_group_exclusions: "Exclusions",
  s2_group_other: "Other",
  s2_required: "Decision needed",
  s2_quote_label: "What the policy says",
  s2_rule_label: "How we read it",
  s2_reason_label: "Why this status",
  s2_quote_found: "Quote found in document",
  s2_quote_missing: "Quote not found in document",
  s2_numbers_ok: "Numbers match the quote",
  s2_numbers_bad: "Numbers do not match the quote",
  s2_schema_ok: "Readable rule format",
  s2_confirm: "Confirm",
  s2_correct: "Correct",
  s2_mark_unknown: "Mark unknown",
  s2_view_doc: "View in document",
  s2_close: "Close",
  s2_save: "Save correction",
  s2_cancel: "Cancel",
  s2_continue: "See what you'll pay →",
  s2_gate_reason: "Confirm or mark unknown: {list}",
  s2_page_label: "Page {page} of {total}",
  s2_prev_page: "Previous page",
  s2_next_page: "Next page",
  s2_apportionment_prompt: "Which charges should the proportionate deduction apply to?",
  s2_app_surgeon: "Surgeon fees, OT charges and diagnostics (as defined on page 4)",
  s2_app_all: "All medical expenses except the room itself",
  s2_app_room: "Only room-related charges",
  s2_room_value_label: "Room limit (% of sum insured per day, as a decimal e.g. 0.01)",
  s2_waiting_months_label: "Waiting period (months)",
  s2_no_clauses: "No clauses were found in this document.",
  rule_room_rent_limit: "Room rent limit",
  rule_waiting_period: "Waiting period",
  rule_non_payable: "Non-payable items",
  rule_apportionment_base: "Apportionment base",
  rule_co_payment: "Co-payment",
  rule_deductible: "Deductible",
  rule_proportionate_deduction: "Proportionate deduction",
  rule_exclusion: "Permanent exclusions",

  /* Screen 3 — Simulate */
  s3_title: "What you'll pay",
  s3_your_oop: "Your out-of-pocket",
  s3_oop_caption:
    "Modelled estimate from the policy wording and the hospital estimate — not a claim decision.",
  s3_months_income: "That is about {months} months of this household's average income.",
  s3_range_caption: "Because one clause is unresolved, this is a range, not a single number.",
  s3_range_point: "Point estimate if nothing further is deducted",
  s3_insurer_pays: "Insurer pays (estimate)",
  s3_gross: "Hospital bill (estimate)",
  s3_waterfall_title: "How the bill is split",
  s3_admissible: "Admissible after non-payables",
  s3_show_calc: "Show calculation",
  s3_hide_calc: "Hide calculation",
  s3_check_line: "Check: insurer + you = hospital bill",
  s3_scenario_title: "Try a change",
  s3_room_label: "Room choice",
  s3_room_above: "Above cap ({rate}/day)",
  s3_room_at: "At cap ({rate}/day)",
  s3_room_unknown: "Room cap not known — toggle unavailable",
  s3_continuity_label: "Continuity credit (waiting period served)",
  s3_continuity_on: "Confirmed",
  s3_continuity_off: "Not confirmed",
  s3_bill_label: "Hospital bill (₹)",
  s3_multi_change: "{count} things changed — we can't attribute this to one clause.",
  s3_delta_room: "from the room rent clause (page {page})",
  s3_delta_continuity: "from the waiting period clause (page {page})",
  s3_delta_bill: "from the changed bill estimate",
  s3_unresolved_title: "Unresolved — why the range",
  s3_savings_title: "Paying for it",
  s3_savings_line: "Your savings cover {savings}.",
  s3_gap_line: "Gap after savings in this scenario: {gap}.",
  s3_worst_case:
    "Worst case — if the insurer pays nothing, you would pay the full {gross}. The offers below model borrowing {principal} towards that gap.",
  s3_loans_title: "If you borrowed the gap",
  s3_loans_synthetic: "Synthetic offers — illustrative only, not real products.",
  s3_col_offer: "Offer",
  s3_col_emi: "EMI / month",
  s3_col_apr_nominal: "APR (nominal)",
  s3_col_apr_effective: "APR (effective)",
  s3_col_total_out: "Total cash out",
  s3_col_lean: "Free cash, worst month",
  s3_lean_caption: "None of these loans is serviceable in your worst month.",
  s3_lean_bar_label: "Free cash left in your worst month, per offer",
  s3_to_plan: "What to do next →",
  s3_assumptions_title: "Assumptions in this calculation",
  s3_assump_month: "Policy month at admission: {month}",
  s3_assump_si: "Sum insured: {si}",
  s3_assump_nonpayable: "Non-payable items in this bill: {amount}",
  s3_assump_base: "Proportionate deduction applies to: {base}",
  base_surgeon_ot_diagnostics: "surgeon fees, OT charges and diagnostics",
  base_all_medical_expenses: "all medical expenses except the room",
  base_room_related_only: "room-related charges only",
  base_unresolved: "not resolved — result shown as a range",

  /* Screen 4 — Plan */
  s4_title: "What to do",
  s4_intro:
    "Ranked by the rupees at stake on this estimate. Each step is a question to confirm — none of them guarantees a claim outcome.",
  s4_worth: "At stake: {amount}",
  s4_draft_title: "Draft message to the insurer",
  s4_draft_label: "This is a draft. Check every figure before you send it.",
  s4_copy: "Copy",
  s4_copied: "Copied",
  s4_unresolved_title: "Still unresolved",
  s4_none_unresolved: "Nothing is unresolved.",
  s4_disclaimer:
    "These are modelled estimates, not claim decisions. Dhaal does not guarantee any claim outcome.",
  s4_to_audit: "View your data and delete →",
  s4_back_sim: "← Back to the numbers",

  /* Screen 5 — Audit */
  s5_title: "Your data",
  s5_data_title: "What this session holds",
  s5_col_item: "Item",
  s5_col_detail: "Detail",
  s5_row_document: "Document",
  s5_row_purpose: "Purpose",
  s5_purpose_text: "Estimate your out-of-pocket cost for one planned hospital stay.",
  s5_row_pages: "Pages read",
  s5_row_retention: "Retention",
  s5_no_document: "No document in this session.",
  s5_engine_title: "Calculation record",
  s5_engine_version: "Engine version",
  s5_repro:
    "Every figure is computed by a deterministic engine from the inputs below. The same inputs always produce the same result — no AI does arithmetic.",
  s5_runs_title: "Simulation runs",
  s5_run_when: "When",
  s5_run_hash: "Run hash",
  s5_run_insurer: "Insurer (est.)",
  s5_run_you: "You (est.)",
  s5_run_checks: "Checks",
  s5_checks_ok: "Passed",
  s5_no_runs: "No simulations yet.",
  s5_ai_title: "What was sent to an AI provider",
  s5_clauses_title: "Clause statuses",
  s5_delete_title: "Delete this session",
  s5_delete_text:
    "This permanently removes the document, all extracted clauses, and every simulation run in this session.",
  s5_delete_button: "Delete my data",
  s5_delete_prompt: "Type DELETE to confirm",
  s5_delete_confirm: "Delete permanently",
  s5_cancel: "Cancel",
  s5_deleted_title: "Deleted",
  s5_deleted_counts: "Removed {documents} document(s), {clauses} clause(s), {runs} run(s). Verified.",
  s5_start_again: "Start again →",
  s5_language: "Language",
} as const;

export type StringKey = keyof typeof en;

const hi: Record<StringKey, string> = {
  /* Common */
  app_name: "DHAAL",
  loading: "लोड हो रहा है…",
  error_title: "कुछ गड़बड़ हो गई",
  retry: "फिर से कोशिश करें",
  back_home: "← शुरू से",
  fixture_banner: "नमूना डेटा · एक काल्पनिक पॉलिसी और बिल। गणना असली है।",
  you_pay: "आप देंगे",
  status_verified: "सत्यापित",
  status_unverified: "असत्यापित",
  status_unknown: "अज्ञात",
  status_conflicting: "विरोधी",
  status_user_confirmed: "आपने पुष्टि की",
  status_synthetic: "नमूना",
  status_missing: "नहीं मिला",
  page_of: "पृष्ठ {page}",
  session_not_found: "यह सत्र अब मौजूद नहीं है। शायद इसे हटा दिया गया है।",

  /* Screen 1 — Goal */
  s1_title: "आप किस लिए योजना बना रहे हैं?",
  s1_intro:
    "ढाल बताता है कि अस्पताल में भर्ती होने पर बीमा के बाद आपको कितना खर्च करना पड़ सकता है — और हर रुपये के पीछे की पॉलिसी शर्त दिखाता है।",
  s1_goal_procedure: "अस्पताल में कोई ऑपरेशन / प्रक्रिया",
  s1_goal_admission: "योजना बनाकर अस्पताल में भर्ती",
  s1_goal_checking: "बस अपनी पॉलिसी जांच रहे हैं",
  s1_describe_label: "या अपने शब्दों में लिखें",
  s1_describe_placeholder: "जैसे अगले महीने पित्ताशय का ऑपरेशन",
  s1_sample_label: "नमूना डेटा इस्तेमाल करें",
  s1_sample_note: "एक काल्पनिक पॉलिसी (सुरक्षा शील्ड हेल्थ) और नमूना अस्पताल बिल। अपलोड की जरूरत नहीं।",
  s1_upload_label: "आपकी पॉलिसी PDF (सिर्फ टेक्स्ट PDF, अधिकतम 10 MB)",
  s1_upload_hint: "स्कैन किए दस्तावेज़ नहीं पढ़े जा सकते। आप नमूना डेटा इस्तेमाल कर सकते हैं।",
  s1_start: "शुरू करें →",
  s1_starting: "शुरू हो रहा है…",
  s1_choose_file: "PDF फाइल चुनें",
  s1_file_required: "पॉलिसी PDF चुनें, या नमूना डेटा चालू करें।",
  s5_row_source: "दस्तावेज़ स्रोत",
  /* Screen 1 — Policy identification */
  s1_policy_title: "आप किस पॉलिसी के तहत दावा करेंगे?",
  s1_policy_intro:
    "Dhaal का हर आंकड़ा आपकी पॉलिसी की अपनी शर्तों से आना चाहिए। नीचे अपनी सही पॉलिसी खोजें, या अपनी पॉलिसी PDF अपलोड करें।",
  s1_mode_find: "मेरी पॉलिसी खोजें",
  s1_mode_upload: "मेरी पॉलिसी PDF अपलोड करें",
  s1_mode_sample: "नमूना पॉलिसी देखें",
  s1_search_label: "बीमा कंपनी या उत्पाद के नाम से खोजें",
  s1_search_placeholder: "टाइप करना शुरू करें — जैसे Suraksha या AarogyaKavach",
  s1_search_hint:
    "Dhaal केवल वही पॉलिसी शर्तें दिखा सकता है जो वास्तव में उसके पास हैं और सत्यापित हैं। अगर आपकी पॉलिसी सूची में नहीं है, तो अपनी पॉलिसी PDF अपलोड करें — मिलती-जुलती पॉलिसी कभी न चुनें।",
  s1_searching: "खोजा जा रहा है…",
  s1_search_empty:
    "हमारे पास कोई पॉलिसी इससे मेल नहीं खाती। वर्तनी जांचें, या नीचे अपनी पॉलिसी PDF अपलोड करें।",
  s1_search_error: "खोज नहीं हो पाई। अपना कनेक्शन जांचकर फिर कोशिश करें।",
  s1_version_label: "आपकी पॉलिसी का कौन-सा संस्करण है? अपना पॉलिसी शेड्यूल देखें।",
  s1_effective_from: "शर्तें {date} से प्रभावी",
  s1_fictional_badge: "काल्पनिक नमूना",
  s1_policy_selected: "चुनी गई पॉलिसी",
  s1_change_policy: "बदलें",
  s1_declared_insurer: "बीमा कंपनी (आपके पॉलिसी शेड्यूल से)",
  s1_declared_product: "उत्पाद का नाम (आपके पॉलिसी शेड्यूल से)",
  s1_declared_note:
    "वैकल्पिक, लेकिन 권장 है। Dhaal आपकी अपलोड की गई PDF पढ़ता है; यह उसे किसी आधिकारिक संस्करण से सत्यापित नहीं कर सकता, इसलिए अगले स्क्रीन पर हर शर्त जांचें।",
  s1_need_selection: "आगे बढ़ने के लिए ऊपर अपनी सही पॉलिसी और संस्करण चुनें।",
  s1_uin: "UIN {uin}",

  /* Screen 2 — Review conditions */
  s2_review_title: "अपनी पॉलिसी की शर्तें जांचें",
  s2_review_intro:
    "ये शर्तें दस्तावेज़ में मिलीं। केवल यहीं दिख रही शर्तें आपके खर्च को बदल सकती हैं — आगे बढ़ने से पहले हर शर्त दस्तावेज़ से मिलाकर जांचें।",
  s2_policy_block_title: "जिस पॉलिसी पर गणना होगी",
  s2_source_catalogue: "कैटलॉग से लिया गया सत्यापित दस्तावेज़",
  s2_source_upload: "आपकी अपलोड की गई PDF — किसी आधिकारिक संस्करण से सत्यापित नहीं",
  s2_prov_version: "संस्करण {version}",
  s2_prov_effective: "{date} से प्रभावी",
  s2_prov_hash: "SHA-256 {hash}…",
  s2_declared_badge: "नाम जैसा आपने बताया",
  s2_plain_label: "सरल शब्दों में",
  s2_conditions_label: "लागू है",
  expl_room_pct:
    "कमरे का किराया केवल आपकी बीमा राशि के {pct} प्रति दिन तक ही मिलेगा। उससे ऊपर का खर्च — और संभवतः अन्य खर्चों का एक हिस्सा — आपको देना होगा।",
  expl_room_fixed:
    "कमरे का किराया केवल {amount} प्रति दिन तक ही मिलेगा। उससे ऊपर का खर्च — और संभवतः अन्य खर्चों का एक हिस्सा — आपको देना होगा।",
  expl_apportionment:
    "अगर आपका कमरा सीमा से महंगा है, तो अन्य खर्चों में भी आनुपातिक कटौती हो सकती है। कौन-से खर्च गिने जाएंगे, यह यही दस्तावेज़ तय करता है।",
  expl_initial: "पॉलिसी के पहले {days} दिनों में बीमारियाँ कवर नहीं होतीं{accident}।",
  expl_initial_accident: " (दुर्घटनाएँ पहले दिन से कवर हैं)",
  expl_specified:
    "इस शर्त में सूचीबद्ध बीमारियाँ और प्रक्रियाएँ केवल {months} महीने के लगातार कवर के बाद ही कवर होती हैं।",
  expl_ped:
    "पहले से मौजूद बीमारियाँ केवल {months} महीने के लगातार कवर के बाद ही कवर होती हैं।",
  expl_exclusion: "ये उपचार इस पॉलिसी में कभी कवर नहीं होते।",
  expl_nonpayable:
    "बीमा कंपनी इन चीज़ों के पैसे नहीं देगी, भले ही अस्पताल बिल में जोड़ दे।",
  expl_copay: "हर स्वीकृत दावे की राशि का {pct} आपको स्वयं देना होगा।",
  expl_deductible: "हर दावे के पहले {amount} आपको स्वयं देने होंगे।",

  /* Screen 3 — Claim details */
  s3_claim_title: "इस दावे के बारे में",
  s3_claim_intro:
    "प्रतीक्षा अवधि और अपवर्जन उपचार और आपकी पॉलिसी के इतिहास पर निर्भर करते हैं। यहाँ तथ्य दें — Dhaal अनुमान नहीं लगाएगा, और कोई भी अनिश्चित बात स्पष्ट रूप से अनसुलझी रहेगी।",
  s3_condition_label: "बीमारी / प्रक्रिया",
  s3_condition_unsure: "मुझे निश्चित नहीं है",
  s3_condition_other: "कुछ और (सूची में नहीं)",
  s3_ped_label: "क्या यह उपचार पहले से मौजूद बीमारी के लिए है?",
  s3_yes: "हाँ",
  s3_no: "नहीं",
  s3_unsure: "निश्चित नहीं",
  s3_accident_label: "क्या यह भर्ती किसी दुर्घटना के कारण है?",
  s3_inception_label: "पॉलिसी शुरू होने की तारीख",
  s3_admission_label: "भर्ती की तारीख",
  s3_credit_label: "पूर्व लगातार कवर के गिने गए महीने (पोर्टेबिलिटी)",
  s3_dates_derived: "इन तारीखों से: भर्ती के समय {months} महीने ({days} दिन) का कवर।",
  s3_estimate_note:
    "यह पॉलिसी की शर्तों से निकाला गया एक अनुमान है — बीमा कंपनी द्वारा स्वीकृत निपटान नहीं। असली दावे का आकलन बीमा कंपनी अपनी शर्तों पर करेगी।",


  /* Consent */
  consent_title: "आपकी जानकारी का क्या होगा",
  consent_purpose_h: "उद्देश्य",
  consent_purpose: "इस एक अस्पताल भर्ती के लिए आपकी अनुमानित जेब-खर्च राशि निकालना।",
  consent_docs_h: "दस्तावेज़",
  consent_docs: "आपकी पॉलिसी का टेक्स्ट पढ़कर वे शर्तें खोजी जाती हैं जो आपकी राशि बदलती हैं।",
  consent_retention_h: "कितने समय तक",
  consent_retention: "सिर्फ इसी सत्र के लिए। “आपका डेटा” स्क्रीन से कभी भी हटा सकते हैं।",
  consent_dont_h: "हम क्या नहीं करते",
  consent_dont:
    "हम बीमा या लोन नहीं बेचते, और कभी नहीं कहते कि क्लेम मंज़ूर होगा। सभी आंकड़े आपकी दी जानकारी पर आधारित अनुमान हैं।",

  /* Screen 2 — Evidence */
  s2_title: "आपकी पॉलिसी, शर्त-दर-शर्त",
  s2_doc_meta: "{pages} पृष्ठ",
  s2_unconfirmed: "गणना से पहले {count} ज़रूरी तथ्यों पर आपका निर्णय बाकी है।",
  s2_review: "देखें",
  s2_group_coverage: "कवरेज",
  s2_group_waiting: "प्रतीक्षा अवधि",
  s2_group_limits: "सीमाएं",
  s2_group_exclusions: "अपवाद",
  s2_group_other: "अन्य",
  s2_required: "निर्णय ज़रूरी",
  s2_quote_label: "पॉलिसी में क्या लिखा है",
  s2_rule_label: "हम इसे कैसे पढ़ते हैं",
  s2_reason_label: "यह स्थिति क्यों",
  s2_quote_found: "दस्तावेज़ में उद्धरण मिला",
  s2_quote_missing: "दस्तावेज़ में उद्धरण नहीं मिला",
  s2_numbers_ok: "संख्याएं उद्धरण से मेल खाती हैं",
  s2_numbers_bad: "संख्याएं उद्धरण से मेल नहीं खातीं",
  s2_schema_ok: "नियम प्रारूप पढ़ने योग्य",
  s2_confirm: "पुष्टि करें",
  s2_correct: "सुधारें",
  s2_mark_unknown: "अज्ञात मार्क करें",
  s2_view_doc: "दस्तावेज़ में देखें",
  s2_close: "बंद करें",
  s2_save: "सुधार सेव करें",
  s2_cancel: "रद्द करें",
  s2_continue: "देखें आपको कितना देना होगा →",
  s2_gate_reason: "पुष्टि करें या अज्ञात मार्क करें: {list}",
  s2_page_label: "पृष्ठ {page} / {total}",
  s2_prev_page: "पिछला पृष्ठ",
  s2_next_page: "अगला पृष्ठ",
  s2_apportionment_prompt: "आनुपातिक कटौती किन खर्चों पर लागू होनी चाहिए?",
  s2_app_surgeon: "सर्जन फीस, OT खर्च और जांचें (पृष्ठ 4 की परिभाषा अनुसार)",
  s2_app_all: "कमरे को छोड़कर सभी चिकित्सा खर्च",
  s2_app_room: "सिर्फ कमरे से जुड़े खर्च",
  s2_room_value_label: "कमरा सीमा (प्रति दिन बीमा राशि का %, दशमलव में जैसे 0.01)",
  s2_waiting_months_label: "प्रतीक्षा अवधि (महीने)",
  s2_no_clauses: "इस दस्तावेज़ में कोई शर्त नहीं मिली।",
  rule_room_rent_limit: "कमरा किराया सीमा",
  rule_waiting_period: "प्रतीक्षा अवधि",
  rule_non_payable: "गैर-देय वस्तुएं",
  rule_apportionment_base: "आनुपातिक कटौती का आधार",
  rule_co_payment: "सह-भुगतान",
  rule_deductible: "कटौती योग्य राशि",
  rule_proportionate_deduction: "आनुपातिक कटौती",
  rule_exclusion: "स्थायी अपवर्जन",

  /* Screen 3 — Simulate */
  s3_title: "आपको कितना देना होगा",
  s3_your_oop: "आपकी जेब से",
  s3_oop_caption: "पॉलिसी के शब्दों और अस्पताल अनुमान पर आधारित अनुमान — क्लेम का फैसला नहीं।",
  s3_months_income: "यह इस परिवार की औसत आय के लगभग {months} महीनों के बराबर है।",
  s3_range_caption: "एक शर्त अनसुलझी है, इसलिए यह एक संख्या नहीं, एक सीमा है।",
  s3_range_point: "यदि आगे कोई कटौती न हो तो अनुमान",
  s3_insurer_pays: "बीमा कंपनी देगी (अनुमान)",
  s3_gross: "अस्पताल बिल (अनुमान)",
  s3_waterfall_title: "बिल कैसे बंटता है",
  s3_admissible: "गैर-देय के बाद स्वीकार्य",
  s3_show_calc: "गणना दिखाएं",
  s3_hide_calc: "गणना छिपाएं",
  s3_check_line: "जांच: बीमा कंपनी + आप = अस्पताल बिल",
  s3_scenario_title: "एक बदलाव आज़माएं",
  s3_room_label: "कमरे का चुनाव",
  s3_room_above: "सीमा से ऊपर ({rate}/दिन)",
  s3_room_at: "सीमा पर ({rate}/दिन)",
  s3_room_unknown: "कमरा सीमा ज्ञात नहीं — विकल्प उपलब्ध नहीं",
  s3_continuity_label: "निरंतरता क्रेडिट (प्रतीक्षा अवधि पूरी)",
  s3_continuity_on: "पुष्टि है",
  s3_continuity_off: "पुष्टि नहीं",
  s3_bill_label: "अस्पताल बिल (₹)",
  s3_multi_change: "{count} चीजें बदलीं — इसे एक शर्त से नहीं जोड़ा जा सकता।",
  s3_delta_room: "कमरा किराया शर्त से (पृष्ठ {page})",
  s3_delta_continuity: "प्रतीक्षा अवधि शर्त से (पृष्ठ {page})",
  s3_delta_bill: "बदले हुए बिल अनुमान से",
  s3_unresolved_title: "अनसुलझा — सीमा क्यों है",
  s3_savings_title: "भुगतान की व्यवस्था",
  s3_savings_line: "आपकी बचत {savings} कवर करती है।",
  s3_gap_line: "इस स्थिति में बचत के बाद बची कमी: {gap}।",
  s3_worst_case:
    "सबसे बुरी स्थिति — यदि बीमा कंपनी कुछ न दे, तो आपको पूरा {gross} देना होगा। नीचे के ऑफर उस कमी के लिए {principal} उधार लेने का नमूना दिखाते हैं।",
  s3_loans_title: "यदि कमी उधार ली जाए",
  s3_loans_synthetic: "नमूना ऑफर — सिर्फ समझने के लिए, असली उत्पाद नहीं।",
  s3_col_offer: "ऑफर",
  s3_col_emi: "EMI / माह",
  s3_col_apr_nominal: "APR (नाममात्र)",
  s3_col_apr_effective: "APR (प्रभावी)",
  s3_col_total_out: "कुल दिया गया",
  s3_col_lean: "सबसे कमज़ोर महीने में बची राशि",
  s3_lean_caption: "इनमें से कोई भी लोन आपके सबसे कमज़ोर महीने में नहीं चल सकता।",
  s3_lean_bar_label: "प्रत्येक ऑफर पर सबसे कमज़ोर महीने में बची राशि",
  s3_to_plan: "आगे क्या करें →",
  s3_assumptions_title: "इस गणना की मान्यताएं",
  s3_assump_month: "भर्ती के समय पॉलिसी माह: {month}",
  s3_assump_si: "बीमा राशि: {si}",
  s3_assump_nonpayable: "इस बिल में गैर-देय वस्तुएं: {amount}",
  s3_assump_base: "आनुपातिक कटौती लागू है: {base}",
  base_surgeon_ot_diagnostics: "सर्जन फीस, OT खर्च और जांचें",
  base_all_medical_expenses: "कमरे को छोड़कर सभी चिकित्सा खर्च",
  base_room_related_only: "सिर्फ कमरे से जुड़े खर्च",
  base_unresolved: "तय नहीं — परिणाम सीमा के रूप में दिखाया गया है",

  /* Screen 4 — Plan */
  s4_title: "क्या करना है",
  s4_intro:
    "इस अनुमान में दांव पर लगे रुपयों के क्रम में। हर कदम पुष्टि करने का सवाल है — कोई भी क्लेम की गारंटी नहीं देता।",
  s4_worth: "दांव पर: {amount}",
  s4_draft_title: "बीमा कंपनी को संदेश का मसौदा",
  s4_draft_label: "यह मसौदा है। भेजने से पहले हर आंकड़ा जांच लें।",
  s4_copy: "कॉपी करें",
  s4_copied: "कॉपी हो गया",
  s4_unresolved_title: "अभी भी अनसुलझा",
  s4_none_unresolved: "कुछ भी अनसुलझा नहीं है।",
  s4_disclaimer: "ये मॉडल-आधारित अनुमान हैं, क्लेम के फैसले नहीं। ढाल किसी क्लेम परिणाम की गारंटी नहीं देता।",
  s4_to_audit: "अपना डेटा देखें और हटाएं →",
  s4_back_sim: "← आंकड़ों पर वापस",

  /* Screen 5 — Audit */
  s5_title: "आपका डेटा",
  s5_data_title: "इस सत्र में क्या है",
  s5_col_item: "वस्तु",
  s5_col_detail: "विवरण",
  s5_row_document: "दस्तावेज़",
  s5_row_purpose: "उद्देश्य",
  s5_purpose_text: "एक योजनाबद्ध अस्पताल भर्ती के लिए आपकी जेब-खर्च का अनुमान।",
  s5_row_pages: "पढ़े गए पृष्ठ",
  s5_row_retention: "कितने समय तक",
  s5_no_document: "इस सत्र में कोई दस्तावेज़ नहीं है।",
  s5_engine_title: "गणना रिकॉर्ड",
  s5_engine_version: "इंजन संस्करण",
  s5_repro:
    "हर आंकड़ा नीचे दिए इनपुट से एक निश्चित इंजन निकालता है। वही इनपुट हमेशा वही परिणाम देते हैं — कोई AI गणित नहीं करता।",
  s5_runs_title: "गणना रन",
  s5_run_when: "कब",
  s5_run_hash: "रन हैश",
  s5_run_insurer: "बीमा कंपनी (अनुमान)",
  s5_run_you: "आप (अनुमान)",
  s5_run_checks: "जांच",
  s5_checks_ok: "उत्तीर्ण",
  s5_no_runs: "अभी कोई गणना नहीं हुई।",
  s5_ai_title: "AI प्रदाता को क्या भेजा गया",
  s5_clauses_title: "शर्तों की स्थितियां",
  s5_delete_title: "यह सत्र हटाएं",
  s5_delete_text: "इससे दस्तावेज़, सभी निकाली गई शर्तें और हर गणना रन स्थायी रूप से हट जाएंगे।",
  s5_delete_button: "मेरा डेटा हटाएं",
  s5_delete_prompt: "पुष्टि के लिए DELETE लिखें",
  s5_delete_confirm: "स्थायी रूप से हटाएं",
  s5_cancel: "रद्द करें",
  s5_deleted_title: "हटा दिया गया",
  s5_deleted_counts: "{documents} दस्तावेज़, {clauses} शर्तें, {runs} रन हटाए गए। सत्यापित।",
  s5_start_again: "फिर से शुरू करें →",
  s5_language: "भाषा",
};

export const strings: Record<Lang, Record<StringKey, string>> = { en, hi };

export function t(key: StringKey, lang: Lang, params?: Record<string, string | number>): string {
  let s: string = strings[lang][key];
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      s = s.split(`{${k}}`).join(String(v));
    }
  }
  return s;
}

const STATUS_KEYS: Record<string, StringKey> = {
  verified: "status_verified",
  unverified: "status_unverified",
  unknown: "status_unknown",
  conflicting: "status_conflicting",
  user_confirmed: "status_user_confirmed",
  synthetic: "status_synthetic",
  missing: "status_missing",
};

export function statusLabel(status: string, lang: Lang): string {
  const key = STATUS_KEYS[status];
  return key ? t(key, lang) : status;
}

const RULE_KEYS: Record<string, StringKey> = {
  room_rent_limit: "rule_room_rent_limit",
  waiting_period: "rule_waiting_period",
  non_payable: "rule_non_payable",
  apportionment_base: "rule_apportionment_base",
  co_payment: "rule_co_payment",
  deductible: "rule_deductible",
  proportionate_deduction: "rule_proportionate_deduction",
  exclusion: "rule_exclusion",
};

export function ruleLabel(ruleType: string, lang: Lang): string {
  const key = RULE_KEYS[ruleType];
  return key ? t(key, lang) : ruleType.replaceAll("_", " ");
}

/** Resolve the active language from URL param, then localStorage, else English. */
export function resolveLang(searchParams: URLSearchParams): Lang {
  const fromUrl = searchParams.get("lang");
  if (fromUrl === "hi" || fromUrl === "en") return fromUrl;
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem("dhaal.lang");
    if (stored === "hi" || stored === "en") return stored;
  }
  return "en";
}

export function persistLang(lang: Lang): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("dhaal.lang", lang);
    document.documentElement.lang = lang;
  }
}
