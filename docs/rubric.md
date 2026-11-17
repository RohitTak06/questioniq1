# Difficulty rubric

Judge the question itself, as a typical student of that course would meet it
after attending classes. Marks are hidden, so don't guess them. Don't judge by
length alone: a long question can be easy, and a one-line question can be hard.

## Easy
- What kind of thinking: Remember or Understand. Recall a definition, fact,
  term, list or standard result. Explain a concept in your own words.
- How many steps: one. The answer is something you could have memorised.
- Typical signs:
  - Verbs: define, state, list, name, what is, explain the concept of,
    differentiate between (two standard terms), true/false, fill in the blank
  - No calculation, or one formula applied directly
  - Examples: "Define a B-Tree", "What is the role of KVIC?",
    "State Kuhn's algorithm", "What is Cargo in Rust?"

## Medium
- What kind of thinking: Apply. Use a known method, algorithm or rule on given
  data, or explain how or why something works with examples.
- How many steps: several, but the method is standard and taught in class.
  The student knows what to do once they see the question.
- Typical signs:
  - Verbs: compute, solve, find, apply, show the steps, trace, illustrate,
    discuss with examples, compare (with reasons)
  - A textbook algorithm or formula on new numbers (quick sort trace, Euler's
    method, inventory turnover ratio, Fourier transform of a standard function)
  - Legal or business case questions that apply one rule to a short scenario
  - Examples: "Sort this sequence using quick sort, show every step",
    "Find the eigenvalues of A", "Can B legally recover the amount from A?"

## Hard
- What kind of thinking: Analyse, Evaluate or Create. Design something new,
  prove or derive a result, combine several methods, or judge between options
  and justify the choice.
- How many steps: many, and the student must decide the approach themselves.
- Typical signs:
  - Verbs: design, prove, derive, develop a strategy, evaluate, justify,
    propose, analyse a case study, write a program that...
  - Several concepts must be combined (for example interpolation + error
    analysis + derivative; CNN layer sizes + parameter counts)
  - Open-ended scenarios with no single right answer (network design for a
    campus, a marketing strategy, disaster resilience case study)
  - Full accounts or proofs (prepare a Trading, P&L and Balance Sheet;
    prove f is a homomorphism)

## Skip when
- The OCR text is too garbled to understand what is being asked
- The question is cut off, or merged with another question, so you can't
  judge it as one question
- It's not a question (instructions, a header, a table with no task)
- It's only an MCQ option or a list item from a bigger question

## Borderline cases
- Mixed levels in one question: label by the hardest part a student must
  answer to get full marks.
- "Explain" can be Easy or Medium: Easy if it asks to describe a concept,
  Medium if it needs examples, reasons or a worked illustration.
- A standard method on a big or messy input (long trace, many data rows):
  still Medium, unless the student must also choose or design the method.
- Writing code: Medium if it's a direct textbook routine (build a max heap),
  Hard if it needs its own logic or design (find the max in a queue using only
  queue operations).
- OR questions: label each option separately.
- Still unsure between two levels: pick the lower one and move on. Don't
  revisit it.