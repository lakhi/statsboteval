# Research context

Living document. The canonical submitted abstract is `statsboteval_meicogsci26_abstract.pdf`
(MEi:CogSci Conference 2026); the text below is its faithful Markdown transcription, kept here
so it is diffable and searchable. As the project's design evolves beyond the abstract, record
divergences in `decisions.md`, not by rewriting this transcription.

---

## StatsBotEval: An Automated Evaluation Framework for Student-GenAI Interactions

Akshay Lakhi, Daniel Reiter, Deeviya Francis Xavier, Frank Scharnowski, Leonardo Bergmann
University of Vienna — lakhia92@univie.ac.at

### 1 Background

Usage of generative artificial intelligence (GenAI) by students can lead to performance gains
for the learners, yet undermines the processes that are essential for durable learning
(Yan et al., 2025). Further, increased dependence on GenAI seems to negatively affect
problem-solving and critical thinking skills, unrestricted usage even impairing long-term
knowledge retention. On the other hand, a recent meta-analysis on integrating the cognitive
and emotional aspects of support in AI applications provided evidence for a strong effect on
knowledge acquisition (H. Zhang et al., 2025). These contradictory findings underscore the
tension in the usage of GenAI in educational contexts.

### 2 Research Proposal

Our project attempts to defuse this tension by systematically characterizing how students
interact with GenAI, and how this information can inform an educator's teaching practice. We
propose to develop *StatsBotEval*, an automated evaluation framework for student-GenAI
interactions, where chats come from the *StatsBot*, a ChatGPT-like tool for learning
statistics, in use by the psychology students at the University of Vienna since early 2025.

The research project consists of three milestones. First, we build an educator-facing
dashboard that surfaces StatsBot conversational data in real time, displaying descriptive
statistics on student-GenAI interactions including: (1) topic distribution, (2) temporal usage
patterns, (3) deductive and inductive content classifications, (4) language patterns, and
(5) usage context (e.g. number of users and questions). Within Bergmann et al.'s framework
(2025), deductive classifications assign conversations to predefined, curriculum-derived
topics (e.g., the statistics content listed in u:find), while inductive classifications derive
finer, data-driven categories from the chat content itself.

Second, we conduct an exploratory analysis of the data with machine learning techniques by
relating student chat interactions to course performance and learning challenges. Finally, we
consolidate the empirical findings into a master's thesis by situating them within the
educational-GenAI literature.

### 3 Methods

We already have ethics approval for the project, and plan to develop the system with a
privacy-first and GDPR-compliant approach: chats are linked to course records under
pseudonymous identifiers with direct identifiers stripped before analysis, and the dashboard
reports only aggregated, non-identifying outputs.

For the exploratory analysis, gradient boosted decision trees would be used to understand
individual and collective student learning patterns, how these relate to course performance,
and the challenges students face while learning. SHAP (SHapley Additive exPlanations) would
then identify which learning behaviors drive these predictions, capturing not just each
feature's magnitude but also its direction and interactions. We chose interpretable predictive
ML over standard statistical methods to avoid certain known pitfalls, for instance,
cross-validation gives out-of-sample prediction that standard inference usually does not.

### 4 Significance

*StatsBotEval* aims to serve as the evaluation framework for student-GenAI interactions. It
does so by surfacing patterns and insights that instructors can act on to improve their
teaching, and by characterizing the learning challenges students face. *StatsBotEval* would
also help the University of Vienna make more informed decisions about how it integrates GenAI
into its programs. Considering most educational GenAI research comes from East Asia and the
US, this observational study adds a perspective from Central Europe, where students engage
with these tools in German as well as English.

### References

- Bergmann, L., Britz, L., Roth, B., & Tran, U. S. (2025). Mapping psychology students'
  conversations with a large language model (LLM)-powered statistics chatbot – A registered
  report. PCI Registered Report. https://doi.org/10.17605/OSF.IO/V6BJ2
- Yan, L., Greiff, S., Lodge, J. M., & Gašević, D. (2025). Distinguishing performance gains
  from learning when using generative AI. Nature Reviews Psychology, 4(7), 435–436.
  https://doi.org/10.1038/s44159-025-00467-5
- Zhang, H., Liu, Y., Jiang, M., Chen, J., Wang, M., & Paas, F. (2025). Emotional Artificial
  Intelligence in Education: A Systematic Review and Meta-Analysis. Educational Psychology
  Review, 37(4), 106. https://doi.org/10.1007/s10648-025-10086-4

---

## Notes relative to the abstract (current design)

- "Real time" has been reinterpreted as a **weekly batch refresh** (decision D-13 in
  `decisions.md`) — educators check the dashboard week over week.
- The Bergmann et al. framework codes at the **message level**, not the conversation level as
  the abstract's wording suggests; see `bergmann-framework.md`.
- Related resources: OSF project folder https://osf.io/v8ydk/ (referenced by the informed
  consent and the Bergmann study).
