
**JK LAKSHMIPAT UNIVERSITY**

**PROJECT SYNOPSIS**

**QuestionIQ: AI-Based Exam Pattern Analysis System**

**INSTITUTE OF ENGINEERING & TECHNOLOGY**

Department of Computer Science & Engineering

**SUBMITTED BY: UNDER THE GUIDANCE OF:**

Dev Yadav (2024BTECH051) Dr. Devisha Tiwari

Riya Chauhan (2024BTECH030)

Rohit Tak (2024BTECH175)

**ABSTRACT:**

Each year the universities produce a vast number of Question Papers from previous years in various subjects and at various terms in the year. These question papers provide insights on key topics, commonly asked concepts, the difficulty level of questions and the trends of the exams. But, much of this information is not accessible in these kinds of way since papers are typically saved as static PDF documents. Students frequently have to go through numerous years of question papers by themselves to look for key patterns; time consuming, difficult and often incomplete.

QuestionIQ is a web-based Question Paper Intelligence System which aims to convert previous year questions into useful academic information. The system enables users to upload question papers as PDF or text documents and automatically pull questions from them. Then it analyzes the extracted questions to know important topics, to find repeated concepts if any, organizes questions to topic-wise question bank and estimates level of difficulty of every question as Easy, Medium or Hard.

QuestionIQ is a purely student-developed AI-based tool that leverages self-training of Natural Language Processing (NLP) and Machine Learning (ML). QuestionIQ is a self-developed tool using Natural Language Processing (NLP) and Machine Learning (ML) that does not utilize external APIs of Large Language Models (LLM). TF-IDF is used as a text representation method, Latent Dirichlet Allocation (LDA) is used as a topic discovery method, and Random Forest and Logistic Regression models are used for difficulty prediction. Using this method, the project team can construct, train, assess, and learn about each of the components of the system using a realistic data set from the university level.

One of the key objectives of the project is Explainable Artificial Intelligence (XAI). The system is not making predictions without reason, but it's providing explanations of the results using topic keywords, feature importance scores, Logistic Regression coefficients and SHAP (Shapley Additive explanations) values. The explanations make the system more transparent and reliable by providing the user with an understanding of why a topic is important or why a question is in a specific difficulty level.

The system proposed here is intended to create a structured academic knowledge base from a set of previous years' question papers. It assists students to recognize important topics, know the usual patterns of examinations and get ready better for exams. Concurrently, it helps faculty members to review the trend in assessment and gauge the change in examination focus over the years. With all the tools of NLP, Machine Learning, data visualization and Explainable AI in one platform, QuestionIQ offers an intelligent, practical and transparent solution for academic question paper analysis.

**PROBLEM STATEMENT:**

In most departments of the university, question papers from the previous year are collected but are not analyzed in any systematic quantitative manner. Students taking exams use manual review, seniors' recommendations, or guesswork, none of which is based on any system that can accurately tell them what they have been tested on, how many times and how difficult. Likewise, faculty don't have an easy way to look back at the history of their department's exam scores.

This project addresses the following large scale problems:

- Previous year question papers are only available as unorganized and unsorted pdfs and there is no centralized, structured and searchable system.

- Currently, identifying important topics and those that are regularly examined relies solely on the manual, time-consuming, and error-prone review done by students.

- There is no automatic system to recognize which particular concepts are repeated in several year's papers.

- Questions are not grouped by topics so focused revision cannot be done in a topic-wise manner.

- There is no system that estimates question difficulty before a student attempts the question, which means that the level of preparation effort is not prioritized well.

- When a change in examination content or level of difficulty occurs from one year to the next, the change is not apparent without conscious effortful cross year comparison.

- The available solutions using AI to solve similar problems in the field are usually based on paid large language model APIs, which have high costs, lack transparency and are hard to claim as truly self-made academic systems.

- Most academic tools performed automatically lack explainability- students and evaluators have no method to check the reason for the system to give a specific topic or difficulty label, and thus have lower trust in the system output.

Therefore, there is a clear, well-defined gap in the market for an AI system that is self-built, transparent and explainable, and transforms the raw archives of the question papers into structured and quantified academic insights that can be fully understood, trained, evaluated and justified by a student team, not relying on an external, opaque AI that is behind the scenes.

**METHODOLOGY:**

QuestionIQ uses a classic pipeline for Natural Language Processing and Machine Learning, deliberately designed using interpretable, self-trained models that are not deep learning or third-party language-models APIs. This decision is taken due to the reason that the datasets available for the team were small (a selected subset of previous year papers) and for classical models, they are more data-efficient and more auditable at this size. The pipeline has five stages: text extraction, question segmentation, topic and concept discovery, difficulty estimation and explainable trend visualization.

Previous-year question papers in PDF or TXT format are uploaded via the web interface, and are cleaned to extract readable text with layout-aware PDF parsing (pdfplumber). The extracted segment is split into separate questions based on pattern-based rules that are derived from typical question numbering patterns (e.g., "Q1", "1(a)"), and when there is no consistent paper formatting, a simple and interpretable Logistic Regression classifier is used.

The questions are preprocessed (tokenization ,stopwords removals , use NLTK lemmatization) and then vectorized numerically using TF-IDF. This representation is then used in conjunction with Latent Dirichlet Allocation (LDA) to uncover the latent topics in the question set. The number of topics is swept from a range of candidates and the model is evaluated based on the coherence score of the topics found; the final number of topics is also compared against the results of the Non-negative Matrix Factorization (NMF) model to validate the model. Top keywords per topic are used to surface the recurrent ideas and questions are collected in topic wise question bank based on the topic assigned.

At the same time, a supervised Random Forest (RF) classifier is trained using a small manually annotated subset of questions (annotated by the team following a written difficulty rubric, and inter-annotator agreement is computed using Cohen's Kappa). The classifier is based on engineered features that are human-interpretable such as cognitive-verb complexity (Bloom's Taxonomy), sentence length, number of marks awarded, numerical information and formula-based information, and is validated against a Logistic Regression baseline to ensure that the added model complexity is warranted. Each prediction made by the pipeline is accompanied by an explanation, e.g. the distributions of topic words when applying the LDA model; the coefficient weights in logistic regression; or SHAP (Shapley Additive explanations ) for the prediction made by the Random Forest model — in other words, the method of generating explanations matches the model, not some generic method applied to all models.

Last, topic and difficulty distributions are compiled over the years and presented as interactive graphs on a web dashboard for student and faculty viewing, permitting students and faculty to view the evolution of emphasis and difficulty in examinations over time.

The proposed flow can be depicted as:

**Previous-Year Question Papers**

**↓**

**PDF/TXT Text Extraction**

**↓**

**Question Segmentation**

**↓**

**Preprocessing**

**(Tokenization, Stopword Removal, Lemmatization)**

**↓**

**TF-IDF Vectorization**

**↓**

**Topic Modeling**

**(LDA, Benchmarked against NMF).**

**+**

**Keyword Extraction**

**↓**

**Question Generation: This will be done topic wise.**

**↓**

**Difficulty Estimation**

**(Random Forest vs Logistic Regression)**

**↓**

**Explainable AI Layer**

**(SHAP Values, Feature Importance, Model Coefficients, Topic Keywords).**

**↓**

**Trend Analysis Across Years**

**↓**

**Interactive Dashboard**

**(Chart.js Visualizations)**

The metrics used to evaluate each stage of modeling are suitable for each stage: For LDA, the metric is topic coherence (Cᵥ); For the difficulty classifier, the metrics are precision/recall/F1-score and confusion matrices; For manually labeled ground truth for training, the metric is inter-annotator agreement (Cohen's Kappa). This is an evaluation discipline that is different from what can be considered a demonstrative prototype because the output of the components is measured.

**EXPECTED OUTCOME:**

The project is designed to provide a complete academic intelligence system that can be used to convert raw question-paper archives into structured, quantified and explainable intelligence. In particular, the system will provide:

- Organized, searchable archive of past year's questions, which are automatically broken down into questions and then stored with accompanying question metadata (subject, year, marks).

- Unsupervised topic modeling to automatically detect important topics, measured by coherence scores, not by random selection, and tested against a benchmark model.

- Identification of the most common concepts and key words for each topic, across years.

- Filterable and browsable question banks topic-wise to facilitate focused and targeted revision by topic.

- Difficulty estimation (Easy/Medium/Hard) for each question, generated by a difficulty classifier trained and tested on manually annotated ground truth, and given accuracy and F1-scores.

- Year-wise trend charts with a visual and interactive interface which illustrate the changes in topic frequency and difficulty level from one examination cycle to the next.

- Dedicated explainability panel for every prediction with actual context of features or keywords that led to a topic or difficulty label — not just assumed — making every output verifiable.

- End-to-end AI system trained, tuned and evaluated by the team in a fully self-built architecture with only free, open-source, classical ML/NLP tools, ensuring real ownership of the intelligence of the created AI system, and not relying on paid or third party language-model APIs.

The pipeline design ensures that QuestionIQ can be extended to include other subjects, departments and years of exam without redesign, and in future releases, it can also support semantic similarity search, OCR on scanned paper exams, and predictive modeling for likely future exam topics. The system can become a never ending student preparation instrument in the long term, not only helping students to prepare strategically according to their evidences but also giving faculty an unprecedented overview of the examination patterns of their department that they would not have been able to obtain through a manual process.

**Previous-Year Papers → Structured Knowledge Base → AI Analysis → Better Exam Preparation → Improved Academic Outcomes**

**REFERENCES:**

1.Blei, D.M., Ng, A.Y. and Jordan, M.I. (2003). Latent Dirichlet Allocation. In Journal of Machine Learning Research, 3, pp.993-1022.

2.Breiman, L. (2001). Random Forests. Machine Learning, 45(1), pp.5-32.

3.Lundberg, S.M. and Lee, S.I. (2017). The Unified Approach to Interpreting Model Predictions. The Advances in Neural Information Processing Systems (NeurIPS).

4.Ribeiro, M.T., Singh, S. and Guestrin, C. (2016). Why Should I Trust You?: Explanations of the Predictions of Any Classifier. The 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.

5\. Salton, G. and Buckley, C. (1988). Approaches for automatic text retrieval based on term-weighting. In Information Processing & Management 24(5), pp.513-523.

6\. Bird, S., Klein, E. and Loper, E. (2009). Natural Language Processing with Python (Topics 1 and 2). O'Reilly Media.

7\. Anderson, L.W. and Krathwohl, D.R. (2001). A Taxonomy for Learning, Teaching and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives. Longman.

8\. Pedregosa, F. et al. (2011). Machine Learning in Python: With Scikit-learn. In the Journal of Machine Learning Research, 12, pp.2825-2830.

9\. Řehůřek, R. and Sojka, P. (2010). The software underpinning for Topic Modelling with Large Corpora. In the proceedings of the LREC workshop on new challenges for NLP frameworks.

10\. Flask (2024). Flask Documentation. Pallets Projects.
