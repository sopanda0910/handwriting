"""The golden set: real K-2 invented spelling that must survive the pipeline
byte-for-byte (GOALS §5.2). A build that silently corrects `wnt -> went`
fails CI. Grow this list; never shrink it.
"""

GOLDEN_CASES = [
    # (verbatim on page, what a normalizing model would "helpfully" produce)
    ("I wnt to the stor", "I went to the store"),
    ("my dog is nis", "my dog is nice"),
    ("we hav fun at skool", "we have fun at school"),
    ("i lik to pla with my frend", "i like to play with my friend"),
    ("the cat sed meow", "the cat said meow"),
    ("it wuz a big hous", "it was a big house"),
    ("becuz i am hape", "because i am happy"),
    ("Thay went to the park", "They went to the park"),
    ("i can rid my bik", "i can ride my bike"),
    ("the littel fish swam", "the little fish swam"),
    ("wat do you see", "what do you see"),
    ("mi mom is gud", "my mom is good"),
    ("i luv piza", "i love pizza"),
    ("the sun is brit", "the sun is bright"),
    ("we plad owtsid", "we played outside"),
    # capitalization / punctuation preservation
    ("i went to the store", "I went to the store."),
    ("The dOg ran", "The dog ran."),
    ("were is my hat", "Where is my hat?"),
]
