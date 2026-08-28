"""Comprehensive test dataset — 50+ topics across diverse domains.

Used by all other test modules as the shared test fixture source.
Each topic entry contains: domain, course, topic, difficulty_level.
"""

# ---------------------------------------------------------------------------
# 50+ topic dataset covering diverse educational domains
# ---------------------------------------------------------------------------

TOPIC_DATASET = [
    # --- Language Learning (15 topics) ---
    {"domain": "Language Learning", "course": "Japanese Language", "topic": "Hiragana", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Japanese Language", "topic": "Katakana", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Japanese Language", "topic": "Basic Kanji", "difficulty_level": "Intermediate"},
    {"domain": "Language Learning", "course": "Japanese Language", "topic": "JLPT N5 Grammar", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Japanese Language", "topic": "Keigo (Formal Speech)", "difficulty_level": "Advanced"},
    {"domain": "Language Learning", "course": "Spanish Language", "topic": "Present Tense Verbs", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Spanish Language", "topic": "Subjunctive Mood", "difficulty_level": "Intermediate"},
    {"domain": "Language Learning", "course": "Spanish Language", "topic": "Spanish Pronunciation", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "French Language", "topic": "French Articles", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "French Language", "topic": "Passé Composé", "difficulty_level": "Intermediate"},
    {"domain": "Language Learning", "course": "Mandarin Chinese", "topic": "Pinyin", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Mandarin Chinese", "topic": "Tones in Mandarin", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Korean Language", "topic": "Hangul Alphabet", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "Arabic Language", "topic": "Arabic Script", "difficulty_level": "Beginner"},
    {"domain": "Language Learning", "course": "German Language", "topic": "German Cases", "difficulty_level": "Intermediate"},

    # --- Computer Science (15 topics) ---
    {"domain": "Computer Science", "course": "Data Structures", "topic": "Binary Search Trees", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Data Structures", "topic": "Hash Tables", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Data Structures", "topic": "Linked Lists", "difficulty_level": "Beginner"},
    {"domain": "Computer Science", "course": "Algorithms", "topic": "Dynamic Programming", "difficulty_level": "Advanced"},
    {"domain": "Computer Science", "course": "Algorithms", "topic": "Graph Traversal", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Algorithms", "topic": "Sorting Algorithms", "difficulty_level": "Beginner"},
    {"domain": "Computer Science", "course": "Machine Learning", "topic": "Gradient Descent", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Machine Learning", "topic": "Neural Networks", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Machine Learning", "topic": "Decision Trees", "difficulty_level": "Beginner"},
    {"domain": "Computer Science", "course": "Web Development", "topic": "REST API Design", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Web Development", "topic": "React Hooks", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Web Development", "topic": "HTML Basics", "difficulty_level": "Beginner"},
    {"domain": "Computer Science", "course": "Database Systems", "topic": "SQL Joins", "difficulty_level": "Beginner"},
    {"domain": "Computer Science", "course": "Database Systems", "topic": "Database Indexing", "difficulty_level": "Intermediate"},
    {"domain": "Computer Science", "course": "Operating Systems", "topic": "Process Scheduling", "difficulty_level": "Advanced"},

    # --- Mathematics (10 topics) ---
    {"domain": "Mathematics", "course": "Calculus", "topic": "Derivatives", "difficulty_level": "Intermediate"},
    {"domain": "Mathematics", "course": "Calculus", "topic": "Integration by Parts", "difficulty_level": "Advanced"},
    {"domain": "Mathematics", "course": "Linear Algebra", "topic": "Matrix Multiplication", "difficulty_level": "Intermediate"},
    {"domain": "Mathematics", "course": "Linear Algebra", "topic": "Eigenvalues and Eigenvectors", "difficulty_level": "Advanced"},
    {"domain": "Mathematics", "course": "Statistics", "topic": "Hypothesis Testing", "difficulty_level": "Intermediate"},
    {"domain": "Mathematics", "course": "Statistics", "topic": "Normal Distribution", "difficulty_level": "Beginner"},
    {"domain": "Mathematics", "course": "Discrete Mathematics", "topic": "Graph Theory", "difficulty_level": "Intermediate"},
    {"domain": "Mathematics", "course": "Discrete Mathematics", "topic": "Proof by Induction", "difficulty_level": "Intermediate"},
    {"domain": "Mathematics", "course": "Algebra", "topic": "Quadratic Equations", "difficulty_level": "Beginner"},
    {"domain": "Mathematics", "course": "Probability", "topic": "Bayes Theorem", "difficulty_level": "Intermediate"},

    # --- Science (10 topics) ---
    {"domain": "Science", "course": "Physics", "topic": "Newton Laws of Motion", "difficulty_level": "Beginner"},
    {"domain": "Science", "course": "Physics", "topic": "Quantum Mechanics Basics", "difficulty_level": "Advanced"},
    {"domain": "Science", "course": "Chemistry", "topic": "Chemical Bonding", "difficulty_level": "Intermediate"},
    {"domain": "Science", "course": "Chemistry", "topic": "Periodic Table", "difficulty_level": "Beginner"},
    {"domain": "Science", "course": "Biology", "topic": "Cell Division", "difficulty_level": "Intermediate"},
    {"domain": "Science", "course": "Biology", "topic": "DNA Replication", "difficulty_level": "Intermediate"},
    {"domain": "Science", "course": "Environmental Science", "topic": "Climate Change", "difficulty_level": "Beginner"},
    {"domain": "Science", "course": "Astronomy", "topic": "Solar System", "difficulty_level": "Beginner"},
    {"domain": "Science", "course": "Neuroscience", "topic": "Synaptic Transmission", "difficulty_level": "Advanced"},
    {"domain": "Science", "course": "Genetics", "topic": "Mendelian Inheritance", "difficulty_level": "Beginner"},

    # --- Business & Finance (5 topics) ---
    {"domain": "Business", "course": "Finance", "topic": "Time Value of Money", "difficulty_level": "Beginner"},
    {"domain": "Business", "course": "Marketing", "topic": "Consumer Behaviour", "difficulty_level": "Intermediate"},
    {"domain": "Business", "course": "Accounting", "topic": "Double Entry Bookkeeping", "difficulty_level": "Beginner"},
    {"domain": "Business", "course": "Economics", "topic": "Supply and Demand", "difficulty_level": "Beginner"},
    {"domain": "Business", "course": "Project Management", "topic": "Agile Methodology", "difficulty_level": "Intermediate"},
]

# Quick-access subsets used by specific test modules
LANGUAGE_TOPICS = [t for t in TOPIC_DATASET if t["domain"] == "Language Learning"]
CS_TOPICS = [t for t in TOPIC_DATASET if t["domain"] == "Computer Science"]
MATH_TOPICS = [t for t in TOPIC_DATASET if t["domain"] == "Mathematics"]
SCIENCE_TOPICS = [t for t in TOPIC_DATASET if t["domain"] == "Science"]
BEGINNER_TOPICS = [t for t in TOPIC_DATASET if t["difficulty_level"] == "Beginner"]
ADVANCED_TOPICS = [t for t in TOPIC_DATASET if t["difficulty_level"] == "Advanced"]
