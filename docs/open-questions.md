# Open questions

External information needed before Phase A/B specs can be signed off. Check items off (and
move durable answers into the relevant doc) as they resolve.

## Wolfgang / ZID — production StatsBot facts

- [ ] **Prod-vs-repo drift:** does production code populate `matnr` and/or `lv`? (Repo
      snapshot never writes them, but the consent names matriculation number as stored.)
- [ ] **Export capabilities:** how can the MySQL data leave the webspace? phpMyAdmin export?
      SSH + mysqldump? cron on the webspace? outbound HTTPS from the webspace? remote DB
      connections? → determines whether the weekly extract is manual or automatable.
- [ ] **Model timeline:** which Azure deployment/model served StatsBot from March 2025 to
      now, with change dates? (No per-row model column — must be reconstructed.)
- [ ] **System prompt:** does the Azure deployment bake in a persona/system prompt, or did
      students talk to a vanilla model? (App code sends none.)
- [ ] **Data volume now:** current counts of students / sessions / messages.

## Leonardo — Bergmann study handover

- [ ] Exact GPT coding prompts (deductive + inductive) and any harness code.
- [ ] The coded dataset, and **what identifies a message** in it (ideally `history.id`).
- [ ] Source of the bachelor/master mapping used in the study.
- [ ] Access to the OSF folder (https://osf.io/v8ydk/) materials.
- [ ] Are the inductive theme lists frozen, or still evolving toward publication?

## Daniel / ethics — protocol confirmations

- [ ] **Pepper custody:** who holds the HMAC pepper (and where is it kept)?
- [ ] **Privacy floor N:** does the protocol imply a minimum cell size? (Working value: 5.)
- [ ] Confirm the local-corpus + cloud-aggregates architecture satisfies the protocol,
      including transient Azure OpenAI processing for classification.
- [ ] Course-records linkage for milestone 2: which records exist (enrollment/withdrawal,
      questionnaires), who provides them, on what key, in what format?

## Team / publication

- [ ] May this repo go public (thesis reproducibility) — co-authors OK with the abstract and
      consent addendum being visible before MEi:CogSci 2026?
