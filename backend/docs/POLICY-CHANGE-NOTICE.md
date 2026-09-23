# Policy change notice — v1.0 → v1.1

Section 11 of the Privacy Policy promises that material changes are
communicated "at least 7 days before they take effect". The documents are dated
**6 October 2026**. That date is only honest if this notice goes out on or
before **29 September 2026**.

**Sending this is a manual step and nobody is going to do it automatically.**
The platform has no announcement mailer; the only bulk path today is whatever
list tooling the team already uses.

---

## Who to send it to

Every founder with an account — including any whose account is paused or
scheduled for deletion. Someone on their way out is still entitled to know what
they were agreeing to.

```sql
select founder_id, email, full_name
  from founders
 where deletion_executed_at is null
   and email not like '%@erased.ally.local'
 order by founder_id;
```

The second condition excludes founders whose erasure has already run and whose
address is now a placeholder. Sending to those would bounce, and worse, would
mean holding a live mailing list of people who asked to be forgotten.

---

## Subject

> We've updated Ally's Terms and Privacy Policy

Not "Important notice" and not "Action required". Nothing is required of them,
nothing about the service is changing, and a subject line that implies otherwise
costs you the one thing that makes the next notice get read.

## Body

> Hello {first name},
>
> We've rewritten parts of Ally's Terms of Service and Privacy Policy. They take
> effect on 6 October 2026.
>
> **Nothing about what we do with your data has changed.** These changes make
> the documents describe what Ally actually does, more accurately than they did
> before. Specifically:
>
> - We no longer describe the policy as proof that we are compliant with the
>   DPDP Act. It sets out the commitments we make to you; whether every control
>   behind them has been independently verified is a separate question and we
>   shouldn't have implied an answer to it.
> - We've corrected how we describe the legal basis for processing your data.
>   The old wording borrowed a term from European law that doesn't exist in the
>   Indian Act.
> - We've removed specific security claims we couldn't evidence, and replaced
>   them with the measures we actually operate.
> - We've committed to telling you and the Data Protection Board about any
>   personal data breach affecting your data — with no severity threshold of our
>   own. The previous wording said we'd tell you about breaches posing
>   "significant risk", which was narrower than the law requires.
> - We've pointed the "your rights" section at the Privacy Centre in your
>   account, which has been able to export, correct and delete your data for a
>   while and which the documents never mentioned.
>
> Read them here: [Privacy Policy](https://<app-host>/privacy) ·
> [Terms of Service](https://<app-host>/terms)
>
> Next time you sign in we'll ask you to confirm you're happy with the updated
> documents. Your existing choices — including whether we may process your
> diagnostic answers — carry across exactly as they are. You can also change any
> of them at any time under Profile → Privacy Centre.
>
> If anything here doesn't sit right, reply to this email or write to
> privacy@goxl.in.
>
> — Ayush, GoXL

## Why the body says what it says

- **It leads with what did not change.** "We've updated our terms" reads as bad
  news by default. The reader's actual question is "what are they taking from
  me", and the answer is nothing.
- **It lists the changes in plain words, not section numbers.** A notice that
  says "we have amended clauses 3, 8 and 9" is a notice nobody reads, and an
  unread notice is not notice.
- **It says the breach wording got *stricter*.** That is the change most in the
  founder's favour and it would be strange to bury it.
- **It warns about the re-consent prompt** so the dialog is expected rather than
  alarming.

---

## Afterwards

1. **Record the send date** — what was sent, to how many people, when. §11 is a
   promise about timing, and the evidence for it is that record. Keep it
   wherever the consent evidence pack lives.
2. **If the notice cannot go out before 29 September**, change the effective
   date in both documents instead of letting the promise slide. It is one string
   in `PrivacyPolicy.jsx` and `TermsOfService.jsx`; a date the documents
   themselves contradict is worse than a later date.
3. **Watch the re-consent take-up.** Nothing is gated on it, so it will be slow:

```sql
select c.privacy_version, count(*)
  from consents c
  join founders f using (founder_id)
 where f.deletion_executed_at is null
 group by 1 order by 1;
```

Everyone still on `1.0` has been shown the dialog and has not yet answered it.
A number that never moves means the dialog is not appearing, not that founders
are refusing.
