# Why this problem

## Who it's for

Families where one person runs a lot of the household and is about to be away: leaving to
work abroad, going into hospital, travelling for months. The first users we designed for are
families of migrant workers in Sri Lanka and the Philippines, because the scale is large, the
absences are long, and the person leaving is often the one who knows how everything works.

| Fact | Source |
|---|---|
| A record **312,836** Sri Lankans left for work abroad in 2024 (185,162 men and 127,674 women). Kuwait (77,546) and the UAE (51,550) were the largest destinations; Japan took 8,665. | Sri Lanka Bureau of Foreign Employment, reported by the [Daily FT, 1 January 2025](https://ft.lk/front-page/2024-sets-record-for-Sri-Lankans-going-abroad-for-work/44-771235) |
| Sri Lanka's workers' remittances reached **USD 8.07 billion** in 2025, up 22.8% from USD 6.57 billion in 2024. | Central Bank of Sri Lanka data, reported by [Ada Derana Biz, 10 January 2026](https://bizenglish.adaderana.lk/sri-lankas-workers-remittances-surpass-usd-8-billion-for-first-time-in-history-in-2025); [CBSL external sector performance, December 2025](https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/press/pr/press_20260130_external_sector_performance_december_2025_e.pdf) |
| **2.19 million** Filipinos worked overseas in 2024; **57.2%** (1.25 million) were women. | Philippine Statistics Authority, reported by [GMA News, 16 December 2025](https://www.gmanetwork.com/news/pinoyabroad/dispatch/969755/ofws-grew-to-2-19m-in-2024-psa/story/) |

Behind each departure is a household that has to keep running: bills, school fees, a
parent's clinic visits, a vehicle's papers, money arriving from abroad. The person leaving
usually does a quick handover the night before. What gets missed is not what they forgot
to write down; it's what nobody realised mattered:

- the school only messages *her* number, and she's taking the SIM;
- the van driver's number is only on *her* phone;
- the clinic book is in a drawer only *she* knows;
- the insurance runs out *during* the absence, and nobody else has done a renewal;
- her husband *could* take her mother to the clinic, except that he drives airport runs on
  Thursday mornings, which is clinic day.

Each of these is small. Together, they are why the first weeks after someone leaves go wrong.

The same shape appears without migration: a planned surgery, a long hospital stay, a
posting to another city. The Jayasinghe sample household (a daughter's two-week hospital stay
while her father needs dialysis three times a week) is there to keep the engine honest about
that.

## What people use today, and the gap

| What people use | What it does well | What it doesn't do |
|---|---|---|
| A handover talk, a notebook, a family WhatsApp group | Quick, personal, in the family's language | Only covers what the person leaving thinks of; nothing checks it against dates, other people's schedules or what is physically where |
| Shared notes and family organiser apps | Lists, calendars, reminders | Store what people already know to write down; can't tell you what's missing or what breaks on which date |
| Password managers with emergency access, digital-legacy services | Secure handover of credentials and documents | Built around secrets and death, not a living household for 90 days; we deliberately *don't* store secrets |
| General AI chat assistants | Can draft a checklist | Plausible but unchecked: no quotes, no simulation, no way to know if the backup person can actually do it |

If I Disappear is different in three ways:

1. **It finds what nobody said.** It works out, for every date of the absence, who would do
   each task, with what, and when, and reports the gaps nobody mentioned. It also sets aside
   the false alarms, with the reason, which is what makes the warnings worth reading.
2. **It plans the smallest fix.** It searches every combination of fixes that fits the time
   the family has before departure, and says what stays open.
3. **It checks the handover.** The person staying explains the task back, by voice or typing;
   a step only counts if they said it.

## Why now

- Gemini can now listen to a rambling voice note, read a photo of a clinic book or a PDF
  insurance schedule, and return structured facts with exact quotes, cheaply enough for a free
  household tool. On the free tier, a router over several Gemini and Gemma models gives one key
  well over a thousand requests a day ([FREE_TIER.md](FREE_TIER.md)).
- Gemini Live makes a spoken practice partner possible on an ordinary phone, with low latency.
- Google ADK workflows let the model calls sit inside a graph of deterministic code, which is
  what makes the answer checkable.

## Beyond households

The same model (people, tasks, routes, resources, time and evidence of handover) fits any
place where critical knowledge sits with one person: a small shop when the owner travels, a
family business, a care team, a school office. That is the path from household impact to
productivity at work, and it's in the [roadmap](ROADMAP.md).
