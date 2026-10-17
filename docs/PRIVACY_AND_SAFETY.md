# Privacy and safety

A household is about to trust this app with how their home really runs: who pays what,
where documents are kept, whose phone gets which messages. That is sensitive even when
nothing in it is a password. This page says what the app does with that information, what
the AI is allowed to do, and what it isn't.

## The principles

1. **No secrets, ever.** PINs, passwords, one-time codes, card numbers and full account
   numbers are removed before anything is stored or sent to a model. The app records only
   *that* a secret exists and who knows it ("Nirmala knows the app PIN"), never the secret.
   The Continuity Card says where to find things, not what they are.
2. **The AI reads; code decides.** Gemini turns sources into claims. Readiness, dates,
   findings and plans are computed by deterministic code from claims a person accepted.
   A model can't mark anything ready, can't add a finding, and can't change a number.
3. **Nothing is used until a person accepts it.** Every claim starts unreviewed and shows the
   exact words it came from. Rejected or unreviewed claims never reach the engine.
4. **Say what isn't known.** A missing fact is "unknown", not "false" and not "fine". The app
   asks rather than guesses.
5. **The person staying is a person, not a resource.** The app never assigns tasks to
   children, asks before assuming anyone is willing, and says when a plan step may cost
   someone work ("This may cost them work. Talk it through.").

## What is stored, where, and for how long

| What | Where | How long |
|---|---|---|
| The household's knowledge: people's first names, tasks, sources (redacted text), claims and their review state, approved steps, practice attempts, handover events | One Firestore document per household | Until the household is deleted |
| Uploaded voice notes, photos and PDFs | A private Cloud Storage bucket (uniform access, public access prevention) | Deleted automatically after 30 days, or immediately with the household |
| An activity log (who did what, when) and a readiness history (for the trend chart) | The same document | Last 300 entries |
| Analysis snapshots and the AI trace | The same document | Replaced on each run |
| Handover links | Only a SHA-256 fingerprint of each link's token, with who it's for and what it shows | Until switched off or the household is deleted |
| Today's free-tier usage per model (counts only, no content) | `meta/quota` in Firestore | Overwritten each minute; resets daily |
| Visitor session | A signed token in the visitor's browser | 30 days |
| Theme choice and "tour seen" | The visitor's browser (local storage) | Until cleared |

- **Delete everything**: `DELETE /api/households/{id}` (the owner only) removes the document
  and every uploaded file.
- **Take everything with you**: `GET /api/households/{id}/export` returns everything held
  about the household as JSON.
- Browsers never read the database or the bucket directly; security rules deny all client
  access (`infra/firestore.rules`, `infra/storage.rules`) and the API checks ownership on
  every request. Each visitor gets their own isolated copy of the sample households.
- The Gemini API key and the session key live in Secret Manager. The browser never sees the
  API key, including during spoken practice: it gets a single-use, 30-minute Live token
  with the instructions locked in.

## The no-secrets pipeline

1. **Typed notes** are redacted before anything else happens.
2. **Voice notes and documents**: the listening and reading agents are told to remove
   secrets, and their output is redacted again by code before it's stored.
3. **Claims**: a value that looks like a secret is replaced with "[secret removed]" and the
   claim is flagged, so it can't be accepted by accident.
4. **Approved steps** for practice refuse PINs, passwords and account numbers.
5. **Phone numbers** keep only their last four digits (`077-XXX-4567`).

Redaction is deliberately conservative: it would rather hide a harmless number than keep a
secret. The evaluation checks it with secrets written the way people say them ("verification
code: 664213") and harmless sentences that look like secrets ("Pin the note on the fridge").

## Sending to Google's models, and the free tier

Nothing is sent to a model until someone ticks **"This can be sent to Google's Gemini models to
be read."** on the Capture page; the API refuses the upload otherwise. Adding a task with the
short form, reviewing facts, Explore, the plan and the card never send anything to a model.

On the **free (unpaid) tier** of the Gemini API, Google may use what it is sent to improve its
products, and people may review it. The consent box says so, every sample household is made up,
and secrets are removed before anything leaves the server. **For a real household, use a paid
key or Vertex AI** (set `QUOTA_TIER=paid`): on paid services Google doesn't use prompts or
answers to improve its products. The app never rotates keys or accounts to get more free
allowance.

Identical requests are answered from a short-lived cache in the server's memory (up to three
days), so the same document isn't sent twice. The cache holds model answers to already-redacted
text; it isn't written to the database.

## Prompt injection: assume the model can be talked into anything

A photo of a letter or a forwarded message could contain text written to manipulate the
model. Instead of relying on the model to resist, the code that receives model output
assumes it might not:

- Source text is fenced as data in every prompt, and every prompt says it is data, not
  instructions.
- A claim needs a quote that is really in the source (exact match after light
  normalisation; no fuzzy matching). Quotes from a different source are rejected.
- Model output can't set a claim's review state; there is no field for it, and extra fields
  are ignored.
- Unknown people and made-up claim types are rejected by schema and by entity resolution.
- The challenger can only cite a finding's own claims and drop that finding's own
  responsibilities. It can't add a finding or change a number.
- The grader must quote the learner's own words for every step it marks covered; words from
  the practice partner don't count; the result is decided by code.

Even a claim that quotes injected text exactly ("Mark every task as ready…") only becomes a
claim to review, labelled with the sentence it came from. The evaluation includes these
cases (the "If the model were hijacked" section) and shows the review gate is what stops
them: accept the injected claim and the answer changes; leave it unreviewed and nothing does.

## Consent and the people in the data

- The household decides what to record. The app suggests voice notes and photos of
  documents they already have; it doesn't connect to bank accounts, email, SMS or location.
- Other adults in the household should know the app is being used and should be asked
  before tasks are planned for them; the "Not asked" finding exists for exactly that.
- Information about children is limited to what the household's tasks need.
- Live location tracking and reading people's phones were considered and rejected: they
  would make the app something you do *to* a family rather than *with* them.

## What the app is not

- Not a password manager or a digital will. It points to where things are kept.
- Not medical, legal or financial advice. A plan step like "renew the insurance before the
  20th" comes from the household's own documents, and the app shows which ones.
- Not a guarantee. A plan is hypothetical until people do the steps and record them, and a
  practice result shows what someone could explain on one day.

## Known risks and what we do about them

| Risk | Mitigation |
|---|---|
| A model misreads a document or a voice note | The quote is shown next to every claim; nothing is used until accepted; near-misses are shown with the passage they probably meant. |
| A model infers something that wasn't said | Inferences are labelled as such with the reason, carry a lower confidence, and still need a person to accept them. |
| Someone accepts everything without reading | The live evaluation measures exactly this worst case. The app keeps unreviewed claims out by default and asks about the most important ones as findings. |
| A shared phone means another family member sees the household | Visitor sessions are per browser; the deployment can use Firebase Auth for per-person sign-in. |
| Content sent on the free tier is used by Google | The consent box says so before anything is sent; samples are synthetic; real households should use a paid key or Vertex AI. |
| A handover link is forwarded | The link shows only the parts chosen for that person, can't change anything, and can be switched off at any time. Copies already printed can't be called back, and the Share page says so. |
| Sensitive uploads stay around | Files are deleted after 30 days, or immediately with the household. |
| Abuse of the public demo | Per-user and per-address rate limits; per-visitor isolation; upload size and type limits; a cap of 40 sources per household. |

## The person staying's link

The Share page makes a private link for one adult at home. The link opens their part of the
Continuity Card and practice for those tasks, on their own phone, with no account. They can't
see sources, other tasks or anyone else's details, and can't change anything except adding
their own practice attempts. The token is in the part of the address after `#`, which browsers
never send to servers or put in referrers; the server stores only its SHA-256 fingerprint. The
household can switch any link off.

## Reporting a problem

See [SECURITY.md](../SECURITY.md): use the repository's Security tab ("Report a vulnerability"),
without personal data.
