# OpenBoard Economy — explained in plain language

*This document explains everything we have built, in simple words. No prior
knowledge needed. If any part is unclear, that is a bug in this document —
tell me and I will rewrite that part.*

---

## 1. The one-sentence version

**We are building a mini economic world inside a computer — a village with a
shared notebook — so we can prove, with experiments, that a fair economy
governed by its citizens actually works, before any real human ever plays it.**

---

## 2. The story of the village (the core analogy)

Imagine a village with around 180 people. Everything we built lives inside
this one picture:

- **The people** are *citizens*. They have needs: every day they want bread,
  water, electricity, milk, a warm home, medicine, books, and so on.
- **The people work together in small groups** called *cooperatives*
  ("co-ops"). A bakery, a flour mill, a farm, a power plant, a fishing crew.
  Everyone in a co-op owns a share of it — there are no outside bosses.
- **Each co-op follows a recipe.** Just like a cake recipe, it says: take
  this much flour and electricity, this many hours of work, and you get this
  much bread. The whole economy is a web of recipes feeding each other:
  the farm grows grain → the mill turns it into flour → the bakery turns it
  into bread → people eat it.
- **Everything the village makes is sold in a daily market** (an auction).
  Citizens buy what they need. Other co-ops buy what they need as
  ingredients.
- **The village has a shared piggy bank** called the Society Pool. When
  society earns something together (a surplus), it goes there and comes back
  to the people as dividends or help.

Our program is that village. One "tick" of the program = one day in the
village. We can run thousands of days in minutes.

---

## 3. The honest notebook (the ledger)

The most important object in the project is the **ledger**. Think of it as a
notebook that records every single thing that happens in the village: every
payment, every purchase, every law, every vote.

Two special properties make this notebook special:

1. **You cannot tear out a page.** New records are added at the end, and each
   page is mathematically glued to the previous one (each page stores a
   "fingerprint" of the page before it). If anyone secretly changes even one
   old entry, the fingerprints stop matching and everyone can see it. This is
   the same trick Bitcoin uses, and it is why the whole history is
   tamper-proof.
2. **The notebook is the boss.** The program never "remembers" anything on
   its own — everything it knows, it knows *because it is written in the
   notebook*. We can erase the program's memory, replay the notebook from
   day one, and get **exactly the same world, cent by cent**. We test this
   constantly ("replay tests"). It means: no cheating, no hidden state, and
   anyone can re-do the maths and check our work.

**Why this matters:** most games can be hacked because the game master can
secretly change things. Here, the history is the referee, and the referee
cannot lie.

---

## 4. The money — 21 million, forever (like a hard currency)

We made one very important design decision, at your request:

> **There is a fixed amount of money: 21,000,000 credits. Ever. It can be
> split into small pieces (down to 0.01), but never increased.**

What this means in the village:

- On day one, **all the money exists**. Each citizen starts with a small
  stake, and the rest sits in the shared Society Pool.
- **Nothing can ever print more.** We found and closed every money-printing
  trick the old system had (wages printing money, new babies printing their
  welcome gift, the dashboard creating founding money out of thin air).
- Today, every coin is a **transfer** from someone to someone else. Money
  only changes hands; it is never conjured from nothing.
- The engine checks a simple law every single day:
  *money in all pockets + money in the pool + money in co-op tills
  = 21,000,000. Always. No exceptions.*

One side-effect we know about and watch: if the village gets richer and more
productive but the money pot stays the same, prices slowly drift **down**
over time — your savings quietly buy more. That is the normal behaviour of
hard money, and we treat it as a game feature to study, not a surprise.

---

## 5. A day in the village (the engine loop)

Every tick, the engine runs the same day, in the same order:

1. **People go to work** — they put work-hours into their co-op's pot.
2. **Co-ops produce** — they run their recipes: burn ingredients, energy and
   pooled work-hours, and put products into their storeroom.
3. **The market opens** — sellers list goods with a price floor (at least
   what it cost to make), buyers bid, and a clearing phase matches them.
   Essentials (bread, water, electricity, medicine…) are served to citizens
   **before** anything else, and fairly — rotating who is served first, not
   just whoever clicks fastest.
4. **People eat** — citizens consume their daily needs. Anything not bought
   that day counts as "unmet need," and if it keeps happening day after day
   the engine raises a flag.
5. **Leftovers go back to society** — surplus money flows into the shared
   pool, which pays dividends and funds new co-ops.
6. **Democracy runs** — citizens propose and vote on rule changes (more
   below).

The whole order is deterministic: same inputs → same day. No randomness
except a seeded random generator that behaves identically on every computer.

---

## 6. The rules are data, and almost everything is votable

The village's rulebook is not hidden in the code — it is a set of
**parameters** stored in the world itself, like a settings page for society:

- How high is the wealth tax? (Off, or light, or firm, or heavy)
- What share of the surplus is paid back to everyone as dividends?
- How long is the work day? How big can a co-op get?
- Should prices be allowed to drop in a sale? Should food rot?

And crucially — **the villagers can vote to change these rules**, and every
change is written into the tamper-proof notebook. There is a small
"constitutional core" (the ledger itself, the money cap, the equality of
votes) that needs a two-thirds super-majority to touch, and everything else
is ordinary, changeable law. **The village is not a fixed utopia — it is a
laboratory where society can rewrite itself.**

---

## 7. The world starts unfair — like the real one

You asked for this, and it is live: the world now begins like the real world
does.

- **One citizen (the richest 1%) owns 50% of ALL the money.** ~10.5 million
  credits. Everyone else shares the other half.
- The Society Pool starts **empty** — society is publicly poor while one
  private person is astronomically rich.
- The wealth tax starts **off**. The world stays frozen at 50/50 until you,
  the player, enact policies.

We verified that this inequality is *stable*: left alone for 30 days, the
rich citizen keeps exactly 50%. It does not heal by itself. **Un-fixing it
is the game.**

---

## 8. The game you actually play (the dashboard)

The dashboard is a website with three screens, built to be understood in
seconds:

1. **🌍 The World** — the home screen. A big one-word verdict banner
   (THRIVING / STRAINED / CRISIS), two charts that matter ("are people
   getting what they need?" and "is wealth staying shared?"), an alert
   strip that only speaks when something is wrong, and a **🧭 Advisor** that
   explains problems in plain sentences: *"175 citizens can't buy bread —
   the workshops that make it can't get their own ingredients"* — with a
   one-click fix button for emergencies.
2. **🧪 The Lab** — the actual game. You get big friendly questions ("How
   hard should society tax the very rich?") with big buttons. Click one and
   the law takes effect immediately in the live world — no parallel test
   worlds, no compare-runs. You watch the consequences, keep what works,
   change what doesn't. Like a real government.
3. **📜 The Chronicle** — your reign written as a story, day by day, in
   plain words: what became unavailable, what you changed, what improved.

**Two safety nets underneath:**

- **Decision save points.** The moment *before* every law you adopt, the
  whole world is frozen automatically. Hate the result? Roll the world back
  to the exact second before your decision and try a different policy.
- **Autosave every 30 seconds.** A server crash can never again erase your
  world (we learned this the hard way and fixed it permanently).

And a game mode for fun: **Break the System** — you play an antagonist
trying to crash the economy, and we score how well the society resists you.
So far, every attack class we threw at it failed.

---

## 9. The citizens think for themselves (bots)

Nobody is in the village by hand — the citizens are small programs ("bots")
with different personalities:

- **Honest workers**: work, buy their needs, save a bit.
- **Strategic producers**: run their co-op — buy ingredients, produce up to
  what demand asks for, list the surplus for sale.
- **Entrepreneurs**: when a good is chronically missing, they **found new
  co-ops** to produce it, all by themselves, through the normal engine rules.
- **Adversaries** (for testing): hoarders, price manipulators, free-riders,
  smugglers — ten kinds of troublemaker we release into simulations to see
  if the system survives them.

One important honesty note: the bots are *scripted* villagers, not
geniuses. When the village gets stuck (a traffic jam where every workshop
waits on every other one), they politely wait forever instead of rioting or
reorganizing. Some of our work has been teaching the village to un-stick
itself; the rest is deliberately left for *you*, the human government, to
solve. That is the game.

---

## 10. How we prove things work (simulations and gates)

We never claim the economy works — we **prove it by running it**:

- A **hardcore gate** simulates 2,000 days of village life and measures, in
  the final 500 days: did every citizen always get their essentials? (bound:
  0 unmet days) Did everyone get their broader goods regularly? (bound: no
  more than a 30-day gap) — and it runs on several different random seeds,
  because a world that only works with one lucky dice-roll is not proven.
- **Adversary campaigns** release all ten troublemaker personalities into
  the world and check the flags stay quiet.
- **Parameter sweeps** — we have run **100+ simulated villages** with
  different rule combinations (tax rates, dividend shares, work rules,
  across multiple seeds) and banked all the results. This is the learning
  campaign: which societies thrive, which collapse, and why.

A real example of why we test this way: we discovered that a co-op's
production was "self-locking" — it produced as much as it sold, and sold as
much as it produced, so *any* level, even a starving trickle, was perfectly
stable forever. No amount of staring at the code would show that. Only
2,000 days of simulated history revealed it, and the fix (producers now also
respond to *unserved demand*, not just past sales) unlocked growth for the
whole economy.

---

## 11. The trust layer: anchoring to Cardano

Everything above lives on our computer, and a sceptic could say: "why
believe your notebook?" So we add a final seal:

- Every day (or every N days), we take the village notebook's fingerprint
  and **write it into the Cardano blockchain** (a public, world-readable
  ledger that no one — including us — can alter).
- After that, anyone can check: *does today's village state really follow
  from the published history?* We cannot secretly rewrite the past without
  it becoming obvious.

The plan: prove it fully on Cardano's **preprod testnet** (free, safe), and
only later, if ever, touch the real mainnet.

---

## 12. Where we are right now (the honest scoreboard)

| Part of the village | Status |
|---|---|
| Tamper-proof ledger + replay | ✅ proven, byte-identical replays |
| Fixed money supply (21M) | ✅ live, invariant exact, all printers closed |
| Recipes, work, production, daily market | ✅ live |
| Citizens' needs, fair distribution, alerts | ✅ live |
| Democracy (proposals, votes, constitutional guard) | ✅ live |
| Entrepreneurship (auto-founding co-ops) | ✅ live |
| Prices that can fall (clearance sales) | ✅ live |
| Perishable goods (rot) | ✅ live |
| Skills (practice → more output → a bit more pay) | ✅ live |
| Durable machines (capital that wears out slowly) | ✅ live — fixed the whole "breadth" economy |
| Inequality start (1% owns 50%) | ✅ live |
| Dashboard game (World / Lab / Chronicle, advisor, save points) | ✅ live |
| **Hardcore gate: essentials for everyone** | ⚠️ 90% there — a 9-day worst streak remains, root cause proven |
| Cardano anchoring | ✅ built locally, preprod testnet upload is next |
| Multiplayer (several humans at once) | 🚧 built for one human; 10+ seats is Week 3 |

The one remaining gap, in one paragraph: the essential chains (bread, flour,
grain) have too few hands — the bakery has 4 bakers where it needs more to
feed 181 people. Every free worker is already employed, and moving employed
workers between co-ops is a hard design problem (our first attempt, done
bluntly, made the whole economy collapse, so we reverted it and documented
everything). There are four candidate solutions — faster population growth,
bigger co-op size caps as a votable rule, careful worker mobility, or
accepting 90% and moving on to the next phase — and that is a decision we
paused on, by design.

---

## 13. Are we going in the right direction?

What you asked for at the start: *"an economy that runs on transparent
rules, proven by simulation, then grown into games, then into the real
world."*

Where we are on that path:

- **The machinery exists and is honest.** The notebook, the fixed money, the
  market, the votes — all built, all tested, all replayable.
- **The system explains itself.** The advisor, the board, and the chronicle
  answer "what's wrong and why" in plain language — that was your request,
  and it is the heart of the design now.
- **The game has stakes.** The world starts unjust on purpose; the player's
  job is to fix it with policies, with a save-point safety net.
- **Nothing is claimed without simulation proof.** Every claim above is
  backed by a test that anyone can re-run.

The next month, in order: prove the unequal world can be *won* (policy paths
from 50/50 down to fair, with the village still fed), harvest the 100+
banked simulations for the stable rule-combinations, open multiplayer
seats, and anchor the notebook to Cardano preprod. Then: v1.0.

*That's the whole machine. If any part of this doesn't click, point at it —
the village metaphor can go one level deeper anywhere.*
