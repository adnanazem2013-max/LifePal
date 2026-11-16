/*
 * LifePal student model
 * ---------------------
 * A transparent, rule-based learner model for teachers. It runs entirely on
 * the device: no AI service, no network. Every reading it produces can be
 * traced back to the observations that caused it.
 *
 * It is observational decision support, NOT a diagnostic instrument. It never
 * labels a student with a condition; it describes patterns, offers hypotheses
 * with their evidence, and suggests classroom strategies and when to involve
 * a specialist.
 *
 * Evidence item: {id, entry, student, date:'YYYY-MM-DD', trait, value:0..100,
 *                 context, subject, note, source}
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.StudentModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // ---------------------------------------------------------------- taxonomy
  // [id, label, question the companion asks when it knows too little]
  const DOMAINS = [
    {id: 'academic', label: 'Academic', short: 'A', traits: [
      ['mastery', 'Subject mastery', 'how did they do on a recent piece of assessed work (e.g. "scored 14/20 in math")?'],
      ['completion', 'Work completion', 'do they usually finish and hand in their work?'],
      ['participation', 'Class participation', 'how much do they contribute in class discussion?'],
      ['independence', 'Independent learning', 'can they get started and keep going without prompting?']]},
    {id: 'cognitive', label: 'Intellectual', short: 'I', traits: [
      ['reasoning', 'Reasoning & problem solving', 'how do they handle a problem they have not seen before?'],
      ['memory', 'Memory & recall', 'how well do they recall what was taught last week?'],
      ['attention', 'Focus & attention', 'how long can they stay focused on one task?'],
      ['curiosity', 'Curiosity', 'do they ask questions or explore beyond what is required?'],
      ['creativity', 'Creativity', 'have you seen original ideas or unusual approaches from them?'],
      ['expression', 'Communication', 'how clearly do they explain their thinking, aloud or in writing?']]},
    {id: 'emotional', label: 'Emotional intelligence', short: 'E', traits: [
      ['selfAwareness', 'Self-awareness', 'can they name what they feel or what they find hard?'],
      ['selfRegulation', 'Self-regulation', 'how do they react when something goes wrong or feels unfair?'],
      ['motivation', 'Inner motivation', 'do they work because they want to, or only when pushed?'],
      ['empathy', 'Empathy', 'how do they respond when a classmate is struggling or upset?'],
      ['socialSkills', 'Social skills', 'how do they handle disagreement or joining a group?']]},
    {id: 'behavior', label: 'Behavior', short: 'B', traits: [
      ['engagement', 'Engagement', 'how engaged did they seem in lessons this week?'],
      ['conduct', 'Classroom conduct', 'how do they respond to classroom rules and instructions?'],
      ['persistence', 'Persistence', 'what do they do when a task gets difficult?'],
      ['collaboration', 'Collaboration', 'how do they work with a partner or in a group?'],
      ['attendance', 'Attendance & punctuality', 'have they been present and on time lately?']]},
    {id: 'wellbeing', label: 'Wellbeing & life', short: 'W', traits: [
      ['mood', 'Mood', 'how has their mood seemed lately?'],
      ['energy', 'Energy', 'do they seem rested and alert, or tired?'],
      ['confidence', 'Self-confidence', 'do they believe they can succeed at new things?'],
      ['calm', 'Calm (low stress)', 'do they seem relaxed, or worried and tense?'],
      ['belonging', 'Peer belonging', 'who do they spend break time with? Do they seem included?']]}
  ];
  const TRAIT = {};
  for (const d of DOMAINS) for (const [id, label, question] of d.traits) TRAIT[id] = {id, label, question, domain: d.id};
  const BY_LABEL = {};
  for (const id in TRAIT) BY_LABEL[TRAIT[id].label] = id;
  const CONTEXTS = ['Whole class', 'Group work', 'Independent work', 'Test / quiz', 'Transitions', 'Break / recess', 'Morning', 'Afternoon'];
  const SUBJECTS = ['Math', 'Science', 'Reading', 'Writing', 'Language', 'History', 'Geography', 'Art', 'Music', 'PE', 'Computing', 'General'];
  const RATINGS = [[10, '1 · Significant difficulty'], [30, '2 · Often struggles'], [50, '3 · Typical / mixed'], [70, '4 · Doing well'], [90, '5 · Clear strength']];
  const DAYS = ['Sundays', 'Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays'];

  // ------------------------------------------------------------------- maths
  const HALF_LIFE = 45;   // days until an observation counts half as much
  const RECENT = 14;      // "lately" window, days
  const PRIOR = 1.2;      // pseudo-observations of doubt; confidence = W/(W+PRIOR)
  const SOURCE_WEIGHT = {teacher: 1, score: 1.2, bot: 0.8, self: 0.7, sample: 1};
  const HIGH = 68, LOW = 42;

  const clamp = (v, a = 0, b = 100) => Math.min(b, Math.max(a, v));
  const dayNum = s => { const [y, m, d] = String(s).split('-').map(Number); return Math.round(Date.UTC(y, m - 1, d) / 864e5); };
  const dateFrom = n => new Date(n * 864e5).toISOString().slice(0, 10);
  const weekday = s => new Date(dayNum(s) * 864e5).getUTCDay();
  const mean = a => a.reduce((n, x) => n + x, 0) / a.length;
  const firstName = s => String(s.title || '').trim().split(/\s+/)[0] || 'This student';
  const list = a => a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1];
  const confWord = c => c < 0.35 ? 'low' : c < 0.65 ? 'medium' : 'high';

  /** Recency-weighted estimate of one trait from its evidence. */
  function estimate(items, today) {
    if (!items.length) return {n: 0, score: null, confidence: 0, trend: 0, volatility: 0, lastSeen: null};
    const T = dayNum(today);
    let W = 0, S = 0, last = items[0].date;
    const pts = items.map(e => {
      const age = Math.max(0, T - dayNum(e.date));
      const w = (SOURCE_WEIGHT[e.source] || 1) * Math.pow(0.5, age / HALF_LIFE);
      W += w; S += w * e.value; if (e.date > last) last = e.date;
      return {age, w, v: e.value};
    });
    const score = S / W;
    const volatility = Math.sqrt(pts.reduce((n, p) => n + p.w * (p.v - score) ** 2, 0) / W);
    const recent = pts.filter(p => p.age <= RECENT).map(p => p.v);
    const earlier = pts.filter(p => p.age > RECENT && p.age <= 90).map(p => p.v);
    const trend = recent.length >= 2 && earlier.length >= 2 ? mean(recent) - mean(earlier) : 0;
    return {n: items.length, score, confidence: W / (W + PRIOR), trend, volatility, lastSeen: last,
      recentMean: recent.length >= 2 ? mean(recent) : score, earlierMean: earlier.length >= 2 ? mean(earlier) : score};
  }
  const known = t => t.n >= 2 && t.confidence >= 0.4;

  // --------------------------------------------------------- strategy library
  const STRATEGY = {
    mastery: ['Run a 5-minute one-to-one check to find the exact step where understanding breaks down.', 'Re-teach that step with a different representation (concrete objects, a drawing, a worked example).'],
    completion: ['Break assignments into smaller parts with a visible checklist.', 'Agree one consistent place and time for handing work in.'],
    participation: ['Give thinking time and let them rehearse an answer with a partner before sharing.', 'Tell them privately in advance which question you will ask them.'],
    independence: ['Provide a "what to do when stuck" card (re-read, look at the example, ask a peer, then ask me).', 'Praise getting started without help, not only finishing.'],
    reasoning: ['Model your own thinking aloud on a similar problem, then fade the support.', 'Use worked examples with one step missing for them to fill in.'],
    memory: ['Use short, spaced retrieval quizzes instead of re-reading.', 'Link new facts to a picture, story or something they already know.'],
    attention: ['Seat them close to the teaching with fewer visual distractions.', 'Chunk tasks into 10-minute blocks with a short movement break between.'],
    curiosity: ['Start topics from a puzzle or a question connected to their interests.', 'Give them a say in what to investigate next.'],
    creativity: ['Offer open-ended tasks with more than one right answer.', 'Let them choose the format for showing what they learned.'],
    expression: ['Provide sentence starters and key vocabulary before speaking or writing.', 'Let them explain an idea to one peer before the whole class.'],
    selfAwareness: ['Use a simple feelings scale at the start of the day.', 'After a task ask "what was easy, what was hard, what would you do differently?"'],
    selfRegulation: ['Agree a calm-down routine and a signal they can use before things escalate.', 'Stay calm and close first; talk about what happened only once they are settled.'],
    motivation: ['Connect tasks to their own interests and give meaningful choices.', 'Set short goals they can reach quickly and make the progress visible.'],
    empathy: ['Discuss how characters or classmates might feel in stories and real situations.', 'Give them a helping role and notice it specifically when they show care.'],
    socialSkills: ['Teach and rehearse scripts for joining in, disagreeing and taking turns.', 'Pair them with a patient, socially confident classmate.'],
    engagement: ['Open lessons with an active task rather than listening.', 'Check whether the work is too easy or too hard; both look like disengagement.'],
    conduct: ['State expectations positively and privately; catch them doing it right.', 'Look for what the behaviour achieves for them (attention, escape, control) and offer a better route to it.'],
    persistence: ['Praise strategy and effort, and normalise mistakes as part of learning.', 'Start with a task they can succeed at, then raise difficulty gradually.'],
    collaboration: ['Assign clear roles in group work.', 'Begin with pair work before larger groups.'],
    attendance: ['Have a friendly, non-blaming conversation with the family about barriers to getting to school.', 'Make arrival welcoming: a greeting and a predictable first task.'],
    mood: ['Make a quiet moment for a private, low-pressure check-in.', 'Make sure they have at least one trusted adult at school they can go to.'],
    energy: ['Gently ask about sleep, breakfast and what evenings look like.', 'Schedule their most demanding work at the time of day they are most alert.'],
    confidence: ['Arrange small, certain successes and name precisely what they did well.', 'Avoid public comparison; compare them only with their own earlier work.'],
    calm: ['Give advance notice of tests and changes, and teach a simple breathing routine.', 'Reduce time pressure where you can; stress that mistakes are expected.'],
    belonging: ['Engineer structured inclusion: assigned partners, lunchtime clubs, shared jobs.', 'Watch break times discreetly to see who they are (not) with.']
  };
  const ESCALATE = 'If this continues for more than two weeks, or you have any concern for their safety, involve the school counsellor and follow your safeguarding policy.';

  // ------------------------------------------------------------------ profile
  /** Build everything the model believes about one student. */
  function buildProfile(student, evidence, today) {
    const mine = evidence.filter(e => e.student === student.id && TRAIT[e.trait]);
    const name = firstName(student);
    const traits = {};
    for (const id in TRAIT) traits[id] = {id, label: TRAIT[id].label, domain: TRAIT[id].domain, ...estimate(mine.filter(e => e.trait === id), today)};
    const domains = DOMAINS.map(d => {
      const ts = d.traits.map(([id]) => traits[id]), seen = ts.filter(t => t.n);
      const cw = seen.reduce((n, t) => n + t.confidence, 0);
      return {id: d.id, label: d.label, short: d.short, traits: ts, score: seen.length ? seen.reduce((n, t) => n + t.score * t.confidence, 0) / cw : null, confidence: cw / ts.length};
    });
    const lastSeen = mine.reduce((m, e) => e.date > m ? e.date : m, '');
    const firstSeen = mine.reduce((m, e) => e.date < m ? e.date : m, lastSeen);
    const overall = {
      n: mine.length, lastSeen: lastSeen || null,
      daysSince: lastSeen ? Math.max(0, dayNum(today) - dayNum(lastSeen)) : null,
      spanDays: lastSeen ? dayNum(today) - dayNum(firstSeen) + 1 : 0,
      confidence: mean(domains.map(d => d.confidence))
    };
    const all = Object.values(traits);
    const strengths = all.filter(t => known(t) && t.score >= HIGH).sort((a, b) => b.score - a.score);
    const growth = all.filter(t => known(t) && t.score <= LOW + 3).sort((a, b) => a.score - b.score);

    // --- interpretation rules -------------------------------------------
    const t = id => traits[id];
    const lo = (id, th = LOW) => known(t(id)) && t(id).score <= th;
    const hi = (id, th = HIGH) => known(t(id)) && t(id).score >= th;
    const ev = (...ids) => ids.filter(id => t(id).n).map(id => {
      const x = t(id), tr = x.trend <= -10 ? ', falling' : x.trend >= 10 ? ', rising' : '';
      return `${x.label}: ${Math.round(x.score)}/100 from ${x.n} observation${x.n > 1 ? 's' : ''}${tr}`;
    });
    // the traits a strategy should move: the weak ones among an insight's evidence
    const trackable = lines => {
      const all = lines.map(l => ({id: BY_LABEL[l.split(':')[0]], v: Number((l.match(/: (\d+)\/100/) || [])[1])})).filter(x => x.id);
      const weak = all.filter(x => x.v < 60);
      return [...new Set((weak.length ? weak : all).map(x => x.id))];
    };
    const insights = [];
    const add = (kind, severity, id, title, text, evidenceLines, strategies) => insights.push({id, kind, severity, title, text, evidence: evidenceLines, strategies,
      traits: trackable(evidenceLines)});

    const falling = all.filter(x => x.trend <= -15).sort((a, b) => a.trend - b.trend);
    const rising = all.filter(x => x.trend >= 15).sort((a, b) => b.trend - a.trend);
    const lifeTraits = ['mood', 'energy', 'belonging', 'calm', 'confidence'];
    if (falling.length >= 2) {
      const personal = falling.some(x => lifeTraits.includes(x.id));
      add('checkin', personal ? 3 : 2, 'change', 'Recent change worth a check-in',
        `${name}'s ${list(falling.slice(0, 4).map(x => x.label.toLowerCase()))} have dropped over the last two weeks compared with before. A sudden shift across several areas more often reflects something happening in a student's life than a change in ability.`,
        ev(...falling.slice(0, 4).map(x => x.id)),
        ['Find a quiet, private moment for a low-pressure check-in ("I\'ve noticed things seem a bit different lately — how are you doing?").', 'Lower demands slightly for a few days and watch whether things recover.', ESCALATE]);
    } else if (falling.length === 1) {
      const x = falling[0];
      add('pattern', 1, 'dip', `${x.label} is dipping`, `${name}'s ${x.label.toLowerCase()} is about ${Math.round(-x.trend)} points lower over the last two weeks than before.`, ev(x.id), STRATEGY[x.id]);
    }
    if (rising.length) add('strength', 0, 'growth', 'Recent growth',
      `${name} is improving in ${list(rising.slice(0, 3).map(x => x.label.toLowerCase()))}.`, ev(...rising.slice(0, 3).map(x => x.id)),
      ['Tell them specifically what you have noticed improving; named progress tends to stick.']);

    if ((hi('reasoning') || hi('curiosity') || hi('mastery', 75)) && (lo('engagement', 50) || lo('completion', 50) || lo('attention', 46)))
      add('hypothesis', 2, 'underchallenged', 'May be under-challenged',
        `${name} shows strong thinking but low engagement or follow-through. One reading is that the work is not stretching them, and what looks like disinterest is boredom.`,
        ev('reasoning', 'curiosity', 'mastery', 'engagement', 'completion', 'attention'),
        ['Offer a harder or more open version of the same task instead of more of the same.', 'Give them a real problem to investigate and present to the class.', 'Ask them directly what they would find interesting; involve them in setting a goal.']);

    if ((hi('persistence') || hi('completion') || hi('engagement')) && lo('mastery', 52))
      add('hypothesis', 2, 'effort-gap', 'Effort is not yet turning into results',
        `${name} works hard and stays involved, yet assessed results remain low. That usually points to a gap in earlier foundations or to teaching that does not match how they take in information, not to lack of trying.`,
        ev('persistence', 'completion', 'engagement', 'mastery'),
        ['Use a short oral check to find the earliest step they are unsure of, and rebuild from there.', 'Try a different route in: concrete materials, visuals, or talking it through.', 'Praise the strategies that work, not only the effort, so effort stays worth it.', 'If the gap persists across subjects despite support, discuss a learning-support review with your specialist team.']);

    if (hi('mastery', 72) && (lo('calm', 45) || lo('confidence', 45)))
      add('hypothesis', 2, 'pressure', 'High achievement with signs of pressure',
        `${name} achieves well but shows worry or low confidence. Their results may be costing them more than it appears, and fear of mistakes can sit behind strong grades.`,
        ev('mastery', 'calm', 'confidence'),
        ['Praise process and risk-taking rather than perfect scores.', 'Make mistakes safe: share your own, and mark some work for effort only.', 'Check workload and expectations with them and with home.', ESCALATE]);
    else if ((hi('mastery', 65) || hi('reasoning')) && lo('participation', 46))
      add('hypothesis', 1, 'quiet', 'Capable but quiet',
        `${name} understands more than their participation shows. They may need safer ways to contribute.`,
        ev('mastery', 'reasoning', 'participation', 'confidence'), STRATEGY.participation);

    if (lo('selfRegulation'))
      add('hypothesis', lo('conduct', 46) ? 3 : 2, 'regulation', 'Finds strong feelings hard to manage',
        `${name} often struggles to stay regulated when frustrated or upset${lo('conduct', 46) ? ', and it is showing up in behaviour' : ''}. Treat the behaviour as communication: something is too hard, unfair or overwhelming for them in that moment.`,
        ev('selfRegulation', 'conduct', 'calm'), [...STRATEGY.selfRegulation, 'Keep a brief note of what happened just before each incident to find the trigger.']);

    if (lo('attention'))
      add('hypothesis', t('attention').n >= 4 ? 2 : 1, 'attention', 'Sustaining focus is difficult',
        `${name} has found it hard to stay focused across ${t('attention').n} observations. Check sleep, seating, task difficulty and time of day before drawing conclusions.`,
        ev('attention', 'energy', 'engagement'),
        [...STRATEGY.attention, 'If it stays consistent across subjects, settings and weeks, share your notes with the learning-support team; do not label it yourself.']);

    if (lo('belonging') || lo('socialSkills'))
      add('hypothesis', lo('belonging') ? 2 : 1, 'social', lo('belonging') ? 'May feel on the edge of the peer group' : 'Peer interactions are often difficult',
        `${name} shows signs of ${lo('belonging') ? 'being left out or alone' : 'friction with classmates'}. Belonging strongly affects both learning and mood.`,
        ev('belonging', 'socialSkills', 'collaboration', 'mood'), [...STRATEGY.belonging, STRATEGY.socialSkills[0]]);

    if (lo('mood', 40) && !insights.some(i => i.id === 'change'))
      add('checkin', lo('energy') || lo('belonging') ? 3 : 2, 'low-mood', 'Mood has been low for a while',
        `${name}'s mood has been consistently low across ${t('mood').n} observations, not just on one bad day.`,
        ev('mood', 'energy', 'belonging', 'calm'), [...STRATEGY.mood, ESCALATE]);

    if (lo('energy') || lo('attendance', 45))
      add('hypothesis', lo('energy') && lo('attendance', 45) ? 2 : 1, 'life-context', 'Life outside school may be a factor',
        `${name} is often ${lo('energy') ? 'tired' : 'late or absent'}. Sleep, health, responsibilities at home or the journey to school are worth understanding before addressing the learning.`,
        ev('energy', 'attendance'), [STRATEGY.energy[0], STRATEGY.attendance[0]]);

    if (lo('motivation') && !insights.some(i => i.id === 'underchallenged'))
      add('hypothesis', 1, 'motivation', 'Motivation is low', `${name} rarely seems to work from their own interest.`, ev('motivation', 'engagement', 'confidence'), STRATEGY.motivation);

    if (hi('empathy') && (hi('collaboration') || hi('socialSkills')))
      add('strength', 0, 'peer-support', 'Natural peer supporter', `${name} is caring and works well with others.`, ev('empathy', 'collaboration', 'socialSkills'),
        ['Use them as a peer mentor or welcome buddy; it builds their leadership too.', 'Make sure they are also stretched for their own learning, not only helping others.']);
    if (hi('motivation') && hi('independence'))
      add('strength', 0, 'self-driven', 'Self-driven learner', `${name} gets going and keeps going without being pushed.`, ev('motivation', 'independence'), ['Offer longer independent projects and let them set their own goals.']);
    if (hi('curiosity') && hi('creativity'))
      add('strength', 0, 'original', 'Curious, original thinker', `${name} asks questions and comes up with their own ideas.`, ev('curiosity', 'creativity'), ['Give open-ended problems and room to pursue their own questions.']);

    // --- patterns in when / where / what ---------------------------------
    // compare each observation with the student's own level for that trait in the same period,
    // so a recent overall change is not mistaken for a weekday or setting effect
    const T0 = dayNum(today);
    const resid = mine.filter(e => e.trait !== 'mastery' && traits[e.trait].n >= 2).map(e => ({e, r: e.value - (T0 - dayNum(e.date) <= RECENT ? traits[e.trait].recentMean : traits[e.trait].earlierMean)}));
    const group = (keyOf) => { const g = {}; for (const x of resid) { const k = keyOf(x.e); if (k !== '' && k != null) (g[k] = g[k] || []).push(x.r); } return g; };
    if (resid.length >= 8) {
      let worst = null;
      for (const [d, rs] of Object.entries(group(e => weekday(e.date)))) if (rs.length >= 4 && mean(rs) <= -12 && (!worst || mean(rs) < worst.m)) worst = {d, m: mean(rs), n: rs.length};
      if (worst) add('pattern', 1, 'weekday', `Harder ${DAYS[worst.d]}`,
        `Observations of ${name} on ${DAYS[worst.d]} run about ${Math.round(-worst.m)} points below their usual level (${worst.n} observations).`, [],
        [worst.d === '1' ? 'Mondays can reflect the weekend: sleep, a change of household, or dread of the week. Ask gently how weekends go.' : `Look at what is different about ${DAYS[worst.d]}: timetable, a particular lesson, or something at home.`, 'Plan a softer start and a quick personal hello on that day.']);
      for (const [c, rs] of Object.entries(group(e => e.context))) {
        if (rs.length < 5) continue;
        const m = mean(rs);
        if (m <= -14) add('pattern', 1, 'ctx-' + c, `Struggles more in: ${c.toLowerCase()}`, `${name} is about ${Math.round(-m)} points below their usual level in this setting (${rs.length} observations).`, [], ['Prepare them for this setting in advance and add structure or support there first.']);
        else if (m >= 14) add('strength', 0, 'ctx-' + c, `At their best in: ${c.toLowerCase()}`, `${name} is about ${Math.round(m)} points above their usual level in this setting (${rs.length} observations).`, [], ['Use this setting to introduce harder material or to rebuild confidence.']);
      }
    }
    const bySubject = {};
    for (const e of mine) if (e.trait === 'mastery' && e.subject) (bySubject[e.subject] = bySubject[e.subject] || []).push(e.value);
    const subjects = Object.entries(bySubject).filter(([, v]) => v.length >= 2).map(([s, v]) => ({subject: s, score: mean(v), n: v.length})).sort((a, b) => b.score - a.score);
    if (subjects.length >= 2 && subjects[0].score - subjects[subjects.length - 1].score >= 15) {
      const top = subjects[0], low = subjects[subjects.length - 1];
      add('pattern', 1, 'subjects', `Uneven across subjects: strong in ${top.subject}, weaker in ${low.subject}`,
        `${top.subject} averages ${Math.round(top.score)}% and ${low.subject} ${Math.round(low.score)}%. A specific gap is easier to close than a general one.`, [],
        [`Use what works for them in ${top.subject} as a bridge into ${low.subject}.`, STRATEGY.mastery[0]]);
    }
    for (const id of ['mood', 'selfRegulation'])
      if (t(id).n >= 4 && t(id).volatility >= 24) add('pattern', 1, 'volatile-' + id, `${t(id).label} varies a lot from day to day`,
        `${name}'s ${t(id).label.toLowerCase()} swings widely between observations, which suggests specific triggers and not a steady state.`, ev(id), ['Note the time, setting and what happened just before each low point; a trigger usually emerges within a couple of weeks.']);

    if (overall.n && overall.daysSince > RECENT)
      add('pattern', 1, 'unseen', 'Not observed recently', `Nothing has been logged about ${name} for ${overall.daysSince} days, so this picture may be out of date. Quiet students are the easiest to overlook.`, [], ['Make a point of noticing them this week and log one or two observations.']);

    insights.sort((a, b) => b.severity - a.severity);
    const concerns = insights.filter(i => i.severity >= 1 && i.kind !== 'strength');
    const attention = concerns.filter(i => i.kind !== 'pattern' || i.id === 'unseen').reduce((n, i) => n + i.severity, 0) + (overall.n ? 0 : 1);

    // which trait would more evidence help most?
    const gap = all.slice().sort((a, b) => a.confidence - b.confidence || a.n - b.n)[0];
    const nextQuestion = {trait: gap.id, label: gap.label, question: `For ${name}: ${TRAIT[gap.id].question}`};

    const p = {student, name, traits, domains, overall, strengths, growth, insights, concerns, attention, subjects, nextQuestion};
    p.summary = summarize(p);
    return p;
  }

  function summarize(p) {
    const {name, overall} = p;
    if (!overall.n) return `I do not know anything about ${name} yet. Log an observation or tell me what you noticed today.`;
    if (overall.n < 4) return `I am still getting to know ${name}: only ${overall.n} observation${overall.n > 1 ? 's' : ''} so far, so anything I said would be a guess. A few more across different areas will let me start reading patterns.`;
    const out = [];
    if (p.strengths.length) out.push(`${name}'s clearest strengths are ${list(p.strengths.slice(0, 3).map(t => t.label.toLowerCase()))}.`);
    if (p.growth.length) out.push(`The areas needing most support are ${list(p.growth.slice(0, 3).map(t => t.label.toLowerCase()))}.`);
    if (!p.strengths.length && !p.growth.length) out.push(`${name} is in the typical range across what has been observed so far, with nothing standing out strongly yet.`);
    const lead = p.concerns[0];
    if (lead) out.push(lead.text);
    const thin = p.domains.filter(d => d.confidence < 0.25).map(d => d.label.toLowerCase());
    if (thin.length) out.push(`I know little about ${list(thin)} for ${name} so far.`);
    return out.join(' ');
  }

  // ------------------------------------------------- is a strategy working?
  /** Compare the traits a strategy targets before and after it started. */
  function evaluateIntervention(iv, evidence, today) {
    const start = dayNum(iv.start), days = Math.max(0, dayNum(today) - start);
    const rows = iv.traits.filter(id => TRAIT[id]).map(id => {
      const mine = evidence.filter(e => e.student === iv.student && e.trait === id);
      const before = mine.filter(e => { const d = dayNum(e.date); return d < start && d >= start - 28; }).map(e => e.value);
      const after = mine.filter(e => dayNum(e.date) >= start).map(e => e.value);
      return {id, label: TRAIT[id].label, nb: before.length, na: after.length, before: before.length ? mean(before) : null, after: after.length ? mean(after) : null};
    });
    const usable = rows.filter(r => r.nb >= 2 && r.na >= 2);
    if (!usable.length) return {rows, days, change: null, verdict: 'early', text: `Too early to tell (${days} day${days === 1 ? '' : 's'} in). I need at least two observations of ${list(rows.map(r => r.label.toLowerCase()))} before and after the start; keep logging them.`};
    const change = mean(usable.map(r => r.after - r.before));
    const verdict = change >= 8 ? 'helping' : change <= -8 ? 'worse' : days < 10 ? 'early' : 'flat';
    const where = list(usable.map(r => `${r.label.toLowerCase()} ${Math.round(r.before)} → ${Math.round(r.after)}`));
    const text = {
      helping: `It looks like it is helping: ${where}. Keep going, and note that this shows a change after you started, not proof that the strategy caused it.`,
      worse: `Things have got worse since you started: ${where}. Consider stopping or changing the approach, and look for something else that changed at the same time.`,
      flat: `No clear change after ${days} days: ${where}. Give it a little longer, or try a different strategy.`,
      early: `Too early to call (${days} days in): ${where}.`
    }[verdict];
    return {rows, days, change, verdict, text};
  }

  /** Whole-class view: profiles ranked by who most needs the teacher. */
  function classSummary(classroom, today) {
    const profiles = classroom.students.map(s => buildProfile(s, classroom.evidence, today)).sort((a, b) => b.attention - a.attention || a.name.localeCompare(b.name));
    const domains = DOMAINS.map((d, i) => {
      const xs = profiles.map(p => p.domains[i].score).filter(x => x != null);
      return {id: d.id, label: d.label, score: xs.length ? mean(xs) : null};
    });
    return {
      profiles, domains,
      attention: profiles.filter(p => p.attention >= 2),
      unseen: profiles.filter(p => !p.overall.n || p.overall.daysSince > RECENT),
      evidenceCount: profiles.reduce((n, p) => n + p.overall.n, 0)
    };
  }

  // ------------------------------------------------- reading teacher language
  // [pattern, trait, value]. Matched on lower-cased text; negation flips value.
  const LEX = [
    [/\b(helped|helps|helping|comfort\w*|kind|kindly|kindness|caring|considerate|thoughtful|shared|sharing|included (a|an|another|the)|empath\w*)\b/g, 'empathy', 85],
    [/\b(teas(ed|es|ing)|mock(ed|s|ing)|bull(ied|ying) (a|another|others?|his|her|their)|unkind|mean to|laughed at|insult\w*)\b/g, 'empathy', 20],
    [/\b(stayed calm|calmed (down|himself|herself|themselves)|composed|self[- ]control|handled (it|that|the \w+) well|managed (his|her|their) (frustration|anger|emotions|feelings)|recovered quickly|patient|patiently)\b/g, 'selfRegulation', 82],
    [/\b(outburst|meltdown|tantrum|lost (his|her|their) temper|yell(ed|s|ing)|shout(ed|s|ing)|scream(ed|s|ing)|threw|stormed (out|off)|angry|anger|furious|aggressive|hit|kicked|pushed|impulsive|frustrated)\b/g, 'selfRegulation', 20],
    [/\b(motivated|eager|enthusias\w*|excited|keen|took (the )?initiative|went beyond|extra work|determined|ambitious)\b/g, 'motivation', 82],
    [/\b(unmotivated|apathetic|doesn'?t care|didn'?t care|indifferent|reluctant|refus(ed|es|ing) to (work|try|start)|bored|no interest|uninterested)\b/g, 'motivation', 22],
    [/\b(reflect(ed|s|ive|ing)|self[- ]aware|recogni[sz]ed (his|her|their)|admitted|apologi[sz]ed|took responsibility|named (his|her|their) feelings|asked for help)\b/g, 'selfAwareness', 80],
    [/\b(blam(ed|es|ing) (others|everyone|classmates?|someone)|denied|unaware|made excuses)\b/g, 'selfAwareness', 25],
    [/\b(led the|leader|leadership|resolved (a |the )?(conflict|argument|disagreement)|mediat\w*|negotiat\w*|made (a )?(new )?friends?|got along|well[- ]liked|communicat(ed|es) (well|clearly))\b/g, 'socialSkills', 82],
    [/\b(argu(ed|es|ing|ment)|fight|fought|fighting|conflict with|quarrel\w*|bossy|interrupt(ed|s|ing)|struggl(ed|es|ing) to (join|share|take turns))\b/g, 'socialSkills', 24],
    [/\b(engaged|on[- ]task|attentive|involved|absorbed|interested|actively)\b/g, 'engagement', 80],
    [/\b(disengaged|off[- ]task|zoned out|bored|checked out|head down|daydream\w*|passive|not interested)\b/g, 'engagement', 24],
    [/\b(focused|concentrat(ed|es|ing)|paid attention|listened (carefully|well)|attentive)\b/g, 'attention', 80],
    [/\b(distract(ed|ing|s|ible)|unfocused|couldn'?t (focus|concentrate|sit still)|fidget\w*|restless|lost focus|inattentive|daydream\w*)\b/g, 'attention', 24],
    [/\b(respectful|polite|followed (the )?(rules|instructions|directions)|well[- ]behaved|cooperative|responsible)\b/g, 'conduct', 80],
    [/\b(disrupt\w*|disrespect\w*|rude|defian\w*|talk(ed|s|ing) back|broke (the |a )?rules?|misbehav\w*|ignored (instructions|the teacher|me)|refused|swore|cheat(ed|ing)|lied|lying)\b/g, 'conduct', 20],
    [/\b(kept (trying|going|working)|persever\w*|persist\w*|didn'?t give up|never gave up|resilien\w*|tried again|stuck with|worked hard|hard[- ]working|great effort|good effort)\b/g, 'persistence', 82],
    [/\b(gave up|give up|gives up|giving up|quit|stopped trying|avoid(ed|s|ing) (the )?(task|work|challenge)|shut down|easily discouraged)\b/g, 'persistence', 22],
    [/\b(collaborat\w*|team ?work|worked well (with|in)|cooperat(ed|es|ing)|good partner|contributed to the group|took turns)\b/g, 'collaboration', 82],
    [/\b(refus(ed|es|ing) to (work with|share|join)|wouldn'?t (share|work with)|dominated the group|left the group)\b/g, 'collaboration', 24],
    [/\b(on time|punctual|perfect attendance)\b/g, 'attendance', 85],
    [/\b(late|tardy|absent|absence|missed (class|school|the lesson)|skipp(ed|ing)|truan\w*|left early)\b/g, 'attendance', 20],
    [/\b(completed|finished|handed in|turned in|submitted|did (his|her|their) homework|organi[sz]ed|well[- ]prepared)\b/g, 'completion', 80],
    [/\b(incomplete|unfinished|forgot (his |her |their |the )?(homework|books?|materials)|missing (homework|work|assignments?)|no homework|didn'?t (finish|complete|hand in|submit|do (his|her|their) homework)|unprepared|disorgani[sz]ed)\b/g, 'completion', 22],
    [/\b(participat(ed|es|ing)|raised (his|her|their) hand|answered (questions|a question)|spoke up|joined (in|the discussion)|volunteered|shared (his|her|their) (ideas?|opinion|thinking))\b/g, 'participation', 82],
    [/\b(silent|didn'?t (speak|participate|contribute|answer)|quiet|wouldn'?t (speak|answer)|reluctant to (speak|answer|share)|shy)\b/g, 'participation', 26],
    [/\b(independent|independently|self[- ]directed|on (his|her|their) own|without (help|prompting|reminders)|self[- ]starter)\b(?! at (break|recess|lunch))/g, 'independence', 82],
    [/\b(needed (a lot of |constant |lots of )?(help|prompting|reminders|support)|dependent on|relied on|couldn'?t start|waited to be told)\b/g, 'independence', 28],
    [/\b(solved|figured out|reasoned|logical|logically|analy[sz]ed|insightful|clever|quickly (understood|grasped)|grasped|understood|made connections|bright|gifted|advanced)\b/g, 'reasoning', 82],
    [/\b(confused|struggl(ed|es|ing) (to understand|with)|couldn'?t (understand|solve|grasp|follow)|didn'?t understand|misunderst\w*|slow to grasp)\b/g, 'reasoning', 28],
    [/\b(remembered|recalled|memori[sz]ed|retained|by heart)\b/g, 'memory', 82],
    [/\b(forg[eo]ts?|forgotten|couldn'?t (remember|recall)|didn'?t remember|needs repetition)\b(?! (his |her |their |the )?(homework|books?|materials))/g, 'memory', 28],
    [/\b(curious|curiosity|asked (a |great |good |many |lots of |deep |thoughtful |interesting )*questions?|wonder(ed|s|ing)|explor(ed|es|ing)|inquisitive|fascinated|wanted to know)\b/g, 'curiosity', 85],
    [/\b(incurious|never asks|no questions|showed no interest)\b/g, 'curiosity', 28],
    [/\b(creativ\w*|imaginat\w*|original (idea|thinking|solution)|invent(ed|ive|s)|innovative|unique (idea|approach|solution)|artistic)\b/g, 'creativity', 85],
    [/\b(articulate[ds]?|express(ed|es) (himself|herself|themselves|it|ideas?) (well|clearly)|explained (it |the \w+ |(his|her|their) \w+ )?(well|clearly)|eloquent|presented (well|confidently)|rich vocabulary|well[- ]written)\b/g, 'expression', 82],
    [/\b(struggl(ed|es|ing) to (explain|express|find words)|couldn'?t (explain|express)|mumbl\w*)\b/g, 'expression', 28],
    [/\b(happy|cheerful|joyful|smil(ed|es|ing)|laugh(ed|s|ing)(?! at)|upbeat|in good spirits|proud)\b/g, 'mood', 82],
    [/\b(sad|unhappy|tearful|cried|crying|cries|upset|(feeling|seemed|looked|seems|looks) (down|low|flat)|low mood|withdrawn|gloomy|miserable|depressed|hopeless|irritable|moody)\b/g, 'mood', 22],
    [/\b(energetic|lively|alert|full of energy|well[- ]rested)\b/g, 'energy', 80],
    [/\b(tired|sleepy|exhausted|asleep|yawn\w*|lethargic|sluggish|drained|no energy|hungry|unwell|sick|headache)\b/g, 'energy', 20],
    [/\b(confident|confidently|self[- ]assured|believ(ed|es) in (himself|herself|themselves)|took (a )?risks?|assertive)\b/g, 'confidence', 82],
    [/\b(insecure|self[- ]doubt\w*|doubt(ed|s) (himself|herself|themselves)|afraid (to|of) (try|trying|fail|failing|be wrong|being wrong|mistakes|answer)|said (he|she|they) (can'?t|couldn'?t)|i can'?t|i'?m (stupid|dumb|bad at)|hesitant|timid|fear of failure|unsure of (himself|herself|themselves))\b/g, 'confidence', 22],
    [/\b(relaxed|at ease|calm|carefree|settled)\b/g, 'calm', 78],
    [/\b(anxious|anxiety|worried|worries|worrying|nervous|stressed|stress|panic\w*|overwhelmed|tense|on edge|perfectionis\w*|stomach ?ache|afraid|scared|fearful)\b/g, 'calm', 20],
    [/\b(played with (friends|others|classmates)|has (good |close |many )?friends|part of the group|welcomed|connected with (peers|classmates))\b/g, 'belonging', 82],
    [/\b(alone|lonely|isolated|left out|excluded|no friends|sat by (himself|herself|themselves)|on (his|her|their) own at (break|recess|lunch)|rejected|picked on|(was|is|being|got|gets) bullied)\b/g, 'belonging', 20],
    [/\b(aced|full marks|top (mark|score|grade)s?|excellent (work|test|result|grade)s?)\b/g, 'mastery', 92],
    [/\b(failed|failing|poor (result|grade|mark|score)s?|low (score|grade|mark)s?)\b/g, 'mastery', 30]
  ];
  const NEGATE = /(?:\bnot|n't|\b(?:didnt|wasnt|isnt|doesnt|cant|couldnt|wont|wouldnt)|\bnever|\bno|\bwithout|\bhardly|\bbarely|\brarely|\bseldom)\s+(?:(?!and\b|but\b|or\b)\w+\s+)?$/;
  const STRONG = /\b(very|really|extremely|so|incredibly|highly|totally|completely|always)\s+$/;
  const MILD = /\b(a bit|a little|slightly|somewhat|sometimes|occasionally|fairly)\s+$/;
  const SUBJECT_WORDS = [[/\bmath(s|ematics)?\b|\balgebra\b|\bgeometry\b/, 'Math'], [/\bscience\b|\bphysics\b|\bchemistry\b|\bbiology\b/, 'Science'], [/\breading\b/, 'Reading'], [/\bwriting\b|\bessay\b|\bspelling\b/, 'Writing'], [/\benglish\b|\barabic\b|\bfrench\b|\bspanish\b|\bhebrew\b|\blanguage\b/, 'Language'], [/\bhistory\b/, 'History'], [/\bgeography\b/, 'Geography'], [/\bart\b|\bdrawing\b/, 'Art'], [/\bmusic\b/, 'Music'], [/\bpe\b|\bsports?\b|\bgym\b/, 'PE'], [/\bcomput\w+\b|\bcoding\b/, 'Computing']];
  const CONTEXT_WORDS = [[/\bgroup\b|\bteam\b|\bpartner\b/, 'Group work'], [/\btest\b|\bquiz\b|\bexam\b/, 'Test / quiz'], [/\brecess\b|\bbreak\b|\blunch\b|\bplayground\b/, 'Break / recess'], [/\btransition\w*\b|\blining up\b|\bbetween lessons\b/, 'Transitions'], [/\bindependent(ly)? work\b|\bseat ?work\b/, 'Independent work'], [/\bmorning\b/, 'Morning'], [/\bafternoon\b/, 'Afternoon']];

  /** Extract trait signals from one clause of free text. */
  function readSignals(clause) {
    const found = [];
    for (const [re, trait, base] of LEX) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(clause))) {
        const before = clause.slice(Math.max(0, m.index - 24), m.index);
        let value = base;
        if (NEGATE.test(before)) value = 100 - value;
        else if (STRONG.test(before)) value = clamp(value + Math.sign(value - 50) * 8, 5, 95);
        else if (MILD.test(before)) value = value - Math.sign(value - 50) * 12;
        found.push({trait, value, phrase: m[0], start: m.index, end: m.index + m[0].length});
      }
    }
    // the longest phrase wins when two readings of the same trait overlap
    found.sort((a, b) => (b.end - b.start) - (a.end - a.start));
    const kept = [];
    for (const f of found) if (!kept.some(k => k.trait === f.trait && f.start < k.end && k.start < f.end)) kept.push(f);
    const subject = (SUBJECT_WORDS.find(([re]) => re.test(clause)) || [])[1];
    const frac = clause.match(/(\d{1,3}(?:\.\d+)?)\s*(?:\/|out of)\s*(\d{1,3})/);
    const pct = clause.match(/(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)/);
    let score = null;
    if (frac && Number(frac[2]) > 0 && Number(frac[1]) <= Number(frac[2])) score = Number(frac[1]) / Number(frac[2]) * 100;
    else if (pct && Number(pct[1]) <= 100) score = Number(pct[1]);
    if (score != null) {
      const i = kept.findIndex(k => k.trait === 'mastery'); if (i >= 0) kept.splice(i, 1);
      kept.push({trait: 'mastery', value: Math.round(score), phrase: (frac || pct)[0], source: 'score'});
    }
    // one reading per trait per clause
    const byTrait = {};
    for (const k of kept) (byTrait[k.trait] = byTrait[k.trait] || []).push(k);
    const signals = Object.values(byTrait).map(ks => ({trait: ks[0].trait, value: Math.round(mean(ks.map(k => k.value))), phrase: ks.map(k => k.phrase).join(', '), source: ks[0].source || 'bot'}));
    return {signals, subject, context: (CONTEXT_WORDS.find(([re]) => re.test(clause)) || [])[1] || ''};
  }

  const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function findStudents(low, students) {
    const hits = [];
    for (const s of students) {
      const full = String(s.title || '').toLowerCase().trim(), first = full.split(/\s+/)[0];
      if (!first) continue;
      const unique = students.filter(o => String(o.title || '').toLowerCase().trim().split(/\s+/)[0] === first).length === 1;
      const m = new RegExp('\\b' + escapeRe(full) + '\\b').exec(low) || (unique && new RegExp('\\b' + escapeRe(first) + "(?:'s)?\\b").exec(low));
      if (m) hits.push({s, at: m.index});
    }
    return hits.sort((a, b) => a.at - b.at).map(h => h.s);
  }

  // -------------------------------------------------------------- companion
  const hasSignalsEarly = low => /\b(was|were|scored|helped|kept|gave up)\b/.test(low);
  const HELP = [
    'I learn each student from what you tell me and what you log. Everything stays on this device.',
    '',
    'Tell me what you noticed, in your own words:',
    '• "Maya helped a classmate and stayed calm after a low quiz score"',
    '• "Omar scored 12/20 in math but kept trying"',
    '• "Daniel was withdrawn and tired yesterday"',
    '',
    'Or ask me:',
    '• "How is Maya doing?" · "Evaluate Lina emotionally"',
    '• "What should I try with Omar?" · "Why?"',
    '• "Any patterns for Daniel?"',
    '• "Who needs attention?" · "Class overview"',
    '• "What should I observe next?"',
    '• "Start tracking a strategy for Omar" then later "Is it working?"',
    '',
    'I describe patterns and possibilities. I do not diagnose, and I am only as good as the observations I am given.'
  ].join('\n');

  const fmtDomain = d => `${d.label} ${d.score == null ? '–' : Math.round(d.score)}`;
  const fmtInsight = i => `• ${i.title} — ${i.text}`;
  const arrow = v => v >= 60 ? '↑' : v <= 40 ? '↓' : '→';

  function profileReply(p, domainId) {
    const o = p.overall;
    if (o.n < 4) return p.summary + '\n\n' + p.nextQuestion.question;
    const lines = [`${p.student.title} · ${o.n} observations over ${Math.max(1, Math.round(o.spanDays / 7))} week(s) · model confidence ${confWord(o.confidence)}`];
    if (domainId) {
      const ds = p.domains.filter(x => domainId === 'full' || domainId.includes(x.id));
      for (const d of ds) {
        lines.push('', `${d.label}: ${d.score == null ? 'no observations yet' : Math.round(d.score) + '/100'} (confidence ${confWord(d.confidence)})`);
        for (const t of d.traits) lines.push(`• ${t.label}: ${t.n ? Math.round(t.score) + (t.trend <= -10 ? ' ↓ falling' : t.trend >= 10 ? ' ↑ rising' : '') + (known(t) ? '' : ' (thin evidence)') : 'not observed yet'}`);
      }
      const rel = p.insights.filter(i => domainId === 'full' || !i.evidence.length && i.kind === 'pattern' || i.evidence.some(e => ds.some(d => d.traits.some(t => e.startsWith(t.label + ':')))));
      if (rel.length) lines.push('', 'How I read it:', ...rel.slice(0, 5).map(fmtInsight));
    } else {
      lines.push(p.domains.map(fmtDomain).join(' · '), '', p.summary);
      const more = p.insights.filter(i => i !== p.concerns[0]).slice(0, 4);
      if (more.length) lines.push('', 'Also worth knowing:', ...more.map(i => `• ${i.title}`));
    }
    lines.push('', 'Ask "what should I try?" for strategies, or "why?" for the evidence. This is an interpretation of classroom observations, not a diagnosis.');
    return lines.join('\n');
  }

  function strategyReply(p) {
    const picks = p.concerns.slice(0, 2);
    if (!picks.length && !p.growth.length) return p.overall.n < 4 ? p.summary : `Nothing about ${p.name} is calling for a change of approach right now. ${p.strengths.length ? `Keep building on ${list(p.strengths.slice(0, 2).map(t => t.label.toLowerCase()))}.` : ''}\n\n${p.nextQuestion.question}`;
    const lines = [`What I would try with ${p.name}:`];
    for (const i of picks) lines.push('', i.title + ':', ...i.strategies.map(s => '• ' + s));
    const covered = picks.flatMap(i => i.evidence).join(' ');
    const extra = p.growth.find(t => !covered.includes(t.label + ':'));
    if (extra) lines.push('', `For ${extra.label.toLowerCase()}:`, ...STRATEGY[extra.id].map(s => '• ' + s));
    lines.push('', 'Try one thing at a time for about two weeks and log what you see, so I can tell you whether it is working.');
    return lines.join('\n');
  }

  /**
   * Handle one teacher message. Pure: returns the reply and any new evidence
   * for the caller to store. opts: {today, focusId, uid}
   */
  function respond(text, classroom, opts = {}) {
    const today = opts.today, students = classroom.students, evidence = classroom.evidence;
    let seq = 0;
    const uid = opts.uid || (() => 'ev-' + Date.now().toString(36) + '-' + (seq++));
    const raw = String(text || '').trim().replace(/[’‘]/g, "'");
    const low = raw.toLowerCase().replace(/\b(did|does|could|would|was|is) not\b/g, "$1n't").replace(/\bcannot\b/g, "can't");
    const mentioned = findStudents(low, students);
    const focus = mentioned[0] || students.find(s => s.id === opts.focusId) || null;
    const done = (reply, extra = {}) => ({reply, evidence: [], interventions: [], focusId: focus ? focus.id : null, ...extra});
    const trials = classroom.interventions || [];
    const prof = s => buildProfile(s, evidence, today);

    if (!raw || /^(help|hi|hello|hey|\?)\b|what can you do|how do (you|i) (work|use)/.test(low)) return done(HELP);
    if (!students.length) return done('There are no students yet. Add a student first, then tell me what you notice about them.');
    const cs = () => classSummary(classroom, today);

    if (/\b(is|was|are|did|does)\b.*\b(it|that|this|the strateg\w*|the plan)\b.*\b(work\w*|help\w*|improv\w*)|how('s| is) (it|that|the strategy) going|\bprogress (on|of) (the )?(strateg|plan)/.test(low)) {
      if (!focus) return done(`Which student do you mean? I know ${list(students.map(firstName))}.`);
      const mine = trials.filter(t => t.student === focus.id);
      if (!mine.length) return done(`I am not tracking any strategy for ${firstName(focus)} yet. Say "start tracking a strategy for ${firstName(focus)}" and I will begin comparing before and after.`);
      return done(mine.map(t => { const r = evaluateIntervention(t, evidence, today); return `${t.title} (started ${t.start}): ${t.strategy}\n${r.text}`; }).join('\n\n'));
    }
    if (/\b(start|begin)\w*\b.*\b(track\w*|monitor\w*|trial|strateg\w*)|\bi('ll| will| am going to|'m going to) (try|use) (that|it|this)|\bwe('re| are) (trying|starting) (that|it|this)/.test(low) && !hasSignalsEarly(low)) {
      if (!focus) return done(`Which student do you mean? I know ${list(students.map(firstName))}.`);
      const p = buildProfile(focus, evidence, today), i = p.concerns.find(c => c.traits.length && c.strategies.length);
      if (!i) return done(`There is nothing specific to track for ${p.name} right now.`);
      if (trials.some(t => t.student === focus.id && t.insight === i.id)) return done(`I am already tracking "${i.title}" for ${p.name}. Ask "is it working?" any time.`);
      const trial = {id: uid(), student: focus.id, insight: i.id, title: i.title, traits: i.traits, strategy: i.strategies[0], start: today};
      return done(`Tracking started for ${p.name}: "${i.title}". The strategy is: ${trial.strategy}\nI will compare ${list(i.traits.map(t => TRAIT[t].label.toLowerCase()))} before and from today. Keep logging observations and ask "is it working?" in a week or two.`, {interventions: [trial]});
    }

    if (/\b(who|which|anyone|any students?)\b.*\b(need|attention|worr|concern|risk|struggl|support|check)/.test(low) || /needs? (my )?attention/.test(low)) {
      const a = cs().profiles.filter(p => p.attention >= 1);
      if (!a.length) return done('No one is standing out as needing extra attention right now, based on what has been logged.');
      return done(['Students I would look at first, most pressing first:', ...a.slice(0, 6).map(p => `• ${p.student.title} — ${p.concerns.slice(0, 2).map(i => i.title.toLowerCase()).join('; ') || 'no observations yet'}`), '', 'Ask me about any of them by name.'].join('\n'));
    }
    if (/\b(who|which)\b.*(haven'?t|not|have i).*(seen|observ|notic|logg|miss)|\bunseen\b|overlook/.test(low)) {
      const u = cs().unseen;
      return done(u.length ? ['I have little or nothing recent on:', ...u.map(p => `• ${p.student.title} — ${p.overall.n ? 'last observed ' + p.overall.daysSince + ' days ago' : 'never observed'}`)].join('\n') : 'You have logged something about every student in the last two weeks.');
    }
    if (!mentioned.length && /\b(class|everyone|all (my |the )?students|whole group|overview)\b/.test(low)) {
      const c = cs();
      return done([`${students.length} students · ${c.evidenceCount} observations`, 'Class averages: ' + c.domains.map(fmtDomain).join(' · '), '', c.attention.length ? `Needing attention: ${list(c.attention.map(p => p.name))}.` : 'No one is flagged for attention.', c.unseen.length ? `Not observed in two weeks: ${list(c.unseen.map(p => p.name))}.` : 'Everyone has been observed in the last two weeks.'].join('\n'));
    }
    if (/what (do|don'?t) you (not )?know|ask me|what should i (observe|watch|look|log|notice)|what (else )?do you need/.test(low)) {
      if (focus) return done(`${prof(focus).nextQuestion.question}\n\nJust answer in your own words and I will learn from it.`);
      const least = cs().profiles.slice().sort((a, b) => a.overall.confidence - b.overall.confidence)[0];
      return done(`I know least about ${least.student.title}. ${least.nextQuestion.question}`, {focusId: least.student.id});
    }

    const question = /\?\s*$/.test(raw) || /^(how|what|why|who|which|tell|show|give|describe|evaluate|assess|explain|is|does|any)\b/.test(low);
    const parsed = low.split(/[.;!\n]+|\s+(?:but|while|whereas)\s+/).map(c => c.trim()).filter(Boolean).map(c => ({clause: c, who: findStudents(c, students), ...readSignals(c)}));
    const hasSignals = parsed.some(c => c.signals.length);

    if (question || !hasSignals) {
      const need = () => done(`Which student do you mean? I know ${list(students.map(firstName))}.`);
      if (/what (should|can|could|do) i (try|do)|strateg|how (can|do|should|could) i (help|support|teach|reach|motivate)|advice|suggest|recommend|what would (you|help)/.test(low)) return focus ? done(strategyReply(prof(focus))) : need();
      if (/\bwhy\b|evidence|how do you know|explain|based on what/.test(low)) {
        if (!focus) return need();
        const p = prof(focus), i = p.concerns[0] || p.insights[0];
        if (!i) return done(p.summary);
        return done([`"${i.title}" for ${p.name} is based on:`, ...(i.evidence.length ? i.evidence : [i.text]).map(e => '• ' + e), '', `Overall model confidence for ${p.name} is ${confWord(p.overall.confidence)}. If this does not match what you see, log what you do see and I will adjust.`].join('\n'));
      }
      if (/pattern|trigger|when does|what days?|which (days?|subjects?|settings?)/.test(low)) {
        if (!focus) return need();
        const p = prof(focus), ps = p.insights.filter(i => i.kind === 'pattern' || i.id.startsWith('ctx-') || i.id === 'change' || i.id === 'growth');
        return done(ps.length ? [`Patterns I see for ${p.name}:`, ...ps.map(fmtInsight)].join('\n') : `I do not see a reliable pattern for ${p.name} yet. Patterns by day, setting and subject need roughly eight or more observations; adding the setting when you log helps.`);
      }
      if (focus && (question || /\b(profile|summary|report|evaluat\w*|assess\w*|psycholog\w*)\b/.test(low) || mentioned.length)) {
        const dom = /psycholog|full (report|profile|evaluation)|everything/.test(low) ? 'full' : /emotion|\beq\b|feeling/.test(low) ? ['emotional', 'wellbeing'] : /academ|grade|score|subject/.test(low) ? 'academic' : /behaviou?r|conduct/.test(low) ? 'behavior' : /intell|cognit|thinking|\biq\b/.test(low) ? 'cognitive' : /well-?being|mood|stress/.test(low) ? 'wellbeing' : null;
        if (question || dom || /\b(profile|summary|report|evaluat\w*|assess\w*)\b/.test(low)) return done(profileReply(prof(focus), dom));
      }
      if (!focus) return need();
      return done(`I could not read a clear signal about ${firstName(focus)} from that. Try describing what they did or how they seemed (for example "was distracted in group work" or "scored 15/20 in science"), or use "Log observation" for a precise rating.`);
    }

    // ---- log what the teacher observed ---------------------------------
    const date = /\byesterday\b/.test(low) ? dateFrom(dayNum(today) - 1) : today;
    const entry = uid();
    const added = [];
    let current = focus ? [focus] : [];
    for (const c of parsed) {
      if (c.who.length) current = c.who;
      for (const s of current) for (const g of c.signals)
        added.push({id: uid(), entry, student: s.id, date, trait: g.trait, value: g.value, context: c.context, subject: g.trait === 'mastery' ? (c.subject || 'General') : '', note: raw.slice(0, 500), source: g.source});
    }
    if (!added.length) return done(`Which student is this about? I know ${list(students.map(firstName))}.`);
    const lines = [];
    const after = evidence.concat(added);
    for (const s of students.filter(s => added.some(a => a.student === s.id))) {
      const mine = added.filter(a => a.student === s.id);
      const before = prof(s), now = buildProfile(s, after, today);
      lines.push(`Noted for ${now.name}${date === today ? '' : ' (yesterday)'}: ${mine.map(a => `${arrow(a.value)} ${TRAIT[a.trait].label}${a.trait === 'mastery' ? ` ${a.value}%${a.subject !== 'General' ? ' in ' + a.subject : ''}` : ''}`).join(', ')}.`);
      const fresh = now.concerns.find(i => !before.insights.some(b => b.id === i.id));
      if (fresh) lines.push(`This changes my reading: ${fresh.title.toLowerCase()}. ${fresh.text}`);
      else if (now.overall.n < 4) lines.push(`That is ${now.overall.n} observation${now.overall.n > 1 ? 's' : ''} so far; I need a few more before I read patterns.`);
    }
    const last = buildProfile(students.find(s => s.id === added[added.length - 1].student), after, today);
    lines.push('', 'To know them better — ' + last.nextQuestion.question);
    return {reply: lines.join('\n'), evidence: added, focusId: last.student.id};
  }

  // ------------------------------------------------------------- sample class
  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  /** Six invented students with distinct stories, for trying the model out. */
  function sampleClass(today) {
    const rnd = rng(11), T = dayNum(today), students = [], evidence = [];
    let c = 0;
    const defs = [
      {name: 'Maya Haddad', note: 'Reads well above grade level.', mid: 62, base: {reasoning: 88, curiosity: 86, memory: 80, creativity: 80, expression: 78, engagement: 40, completion: 42, attention: 45, motivation: 46}, subj: {Math: 88, Science: 86, Reading: 90}},
      {name: 'Omar Khalil', note: 'Eldest of four; helps at home.', mid: 62, base: {persistence: 86, completion: 82, engagement: 78, conduct: 82, motivation: 76, reasoning: 50, memory: 46, confidence: 48}, subj: {Math: 36, Science: 50, Reading: 54}, monday: -24},
      {name: 'Lina Petrova', note: '', mid: 66, base: {completion: 92, reasoning: 82, memory: 84, attention: 80, calm: 28, confidence: 36, mood: 52, participation: 52}, subj: {Math: 92, Science: 90, Reading: 91}},
      {name: 'Daniel Okafor', note: '', mid: 68, base: {}, subj: {Math: 68, Science: 70, Reading: 66}, drop: {mood: -36, engagement: -30, energy: -30, participation: -26, completion: -24, belonging: -26}},
      {name: 'Sara Mansour', note: '', mid: 64, base: {empathy: 90, collaboration: 86, socialSkills: 84, selfRegulation: 78, mood: 78, belonging: 84, conduct: 80, motivation: 74, independence: 72}, subj: {Math: 66, Science: 70, Reading: 74}},
      {name: 'Youssef Amin', note: 'Joined mid-year.', sparse: true}
    ];
    const ids = Object.keys(TRAIT).filter(t => t !== 'mastery');
    const push = (student, age, trait, value, context, subject) => evidence.push({id: 'sample-' + (c++), entry: 'sample-e' + c, student, date: dateFrom(T - age), trait, value: Math.round(clamp(value, 4, 98)), context, subject: subject || '', note: '', source: 'sample'});
    defs.forEach((d, i) => {
      const id = 'stu-' + (i + 1);
      students.push({id, title: d.name, group: 'Grade 6A', note: d.note});
      if (d.sparse) { push(id, 33, 'participation', 30, 'Whole class'); push(id, 30, 'conduct', 70, 'Whole class'); return; }
      const featured = [...Object.keys(d.base), ...Object.keys(d.drop || {})];
      for (let age = 56; age >= 0; age--) {
        const wd = new Date((T - age) * 864e5).getUTCDay();
        if (wd === 0 || wd === 6) continue;
        const count = rnd() < 0.9 ? (rnd() < 0.6 ? 3 : 2) : 0;
        for (let k = 0; k < count; k++) {
          const trait = featured.length && rnd() < 0.65 ? featured[Math.floor(rnd() * featured.length)] : ids[Math.floor(rnd() * ids.length)];
          if (trait === 'mastery') continue;
          const context = CONTEXTS[Math.floor(rnd() * CONTEXTS.length)];
          let v = (d.base[trait] ?? d.mid) + (rnd() - 0.5) * 20;
          if (age <= RECENT && d.drop && d.drop[trait]) v += d.drop[trait];
          if (wd === 1 && d.monday) v += d.monday;
          push(id, age, trait, v, context);
        }
        if (wd === 4 && age % 14 < 7) for (const s of Object.keys(d.subj)) push(id, age, 'mastery', d.subj[s] + (rnd() - 0.5) * 14, 'Test / quiz', s);
      }
    });
    return {students, evidence};
  }

  return {evaluateIntervention, DOMAINS, TRAIT, CONTEXTS, SUBJECTS, RATINGS, STRATEGY, estimate, buildProfile, classSummary, readSignals, findStudents, respond, sampleClass, confWord, known};
});
