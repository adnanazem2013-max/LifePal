# LifePal

A local-first workspace for life and work. Open `index.html` in a browser; nothing is sent anywhere.

## Student model (teacher tools)

The **Student model** page learns each student from what the teacher observes and turns it into a profile, patterns and suggested strategies.

- **Five domains, 25 traits**: academic, intellectual, emotional intelligence, behaviour, wellbeing & life.
- **Learning**: each trait is a recency-weighted average of observations (half weight after 45 days) with a confidence level, a two-week trend and a volatility measure.
- **Interpretation**: transparent rules combine traits into readings such as "may be under-challenged", "effort is not yet turning into results" or "recent change worth a check-in", each with its evidence and things to try. Day-of-week, setting and subject patterns are detected too.
- **Class companion**: type what you noticed in plain words ("Omar scored 12/20 in math but kept trying") and it logs the signals; ask "How is Maya doing?", "Who needs attention?", "What should I try with Omar?", "Why?".

It is decision support, **not a diagnostic or clinical tool**. It is rule-based and runs on the device; student records live in the browser's storage and in exported backups.

Files: `student-model.js` (the engine, no dependencies; must sit next to `index.html`), `tests/student-model.test.js`.

```
node --test tests/*.test.js
```
