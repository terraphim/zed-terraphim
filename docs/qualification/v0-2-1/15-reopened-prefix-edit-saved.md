UPDATED # Why our release notes are too long

I think most of our release notes are basically longer than they need to be. Readers open them to answer one question, which is whether the update changes anything they rely on, and they leave as soon as they have the answer. Every extra paragraph makes that answer harder to find.

The draft for the last release is a good example. It opened with three sentences about the history of the project (which nobody had asked about) before it reached the first change. It then described the new search index in detail, really quite a lot of detail, although only a handful of users ever configure it by hand. The breaking change to the configuration file, the one thing that could actually stop a deployment, appeared near the end, in the second half of a long sentence.

Perhaps the habit comes from how the notes are written. Each engineer adds a paragraph for their own work, usually at the end of a long day, and nobody reads the whole document from the top before it ships. The result is a list of updates in the order they were merged rather than in the order that matters to a reader. It is honestly not anyone's fault, and it is fairly easy to fix.

We could start with a simple rule. The first paragraph should say, in plain words, what a reader has to do after upgrading, and it should say nothing else. If the answer is "nothing", the paragraph can simply say so — readers will be grateful for the time it saves them. Everything that follows is reference material, and reference material can be as detailed as it needs to be, because people only read the parts they search for.

A second rule would help as well. Every change should be described once, in one place, with one sentence of context at most. At the moment the same change is often mentioned in the summary, again in the list of fixes and again in the upgrade guide, each time with slightly different wording, which makes readers wonder whether there are really three separate changes.

It would also be worth keeping a short glossary. Terms such as "haystack", "role" and "thesaurus" are obvious to the people who build the system, but they are not obvious to someone who installed it last week. A glossary of a dozen entries, linked from the notes, would answer most of the questions that currently arrive in the support channel.

None of this needs new tooling. It needs one person to read each draft from start to finish, ask what the reader must do, and delete the rest without too much regret. In my experience the notes get shorter, the questions get fewer, and the people who write the notes end up spending less time on them, not more.


```terraphim-alternatives
{
  "version": 1,
  "spans": [],
  "ghosts": [
    {
      "id": "trim-ghost-1",
      "anchor": {
        "start": 46,
        "end": 54,
        "text": "I think ",
        "before": "our release notes are too long\n\n",
        "after": "most of our release notes are "
      }
    },
    {
      "id": "trim-ghost-2",
      "anchor": {
        "start": 83,
        "end": 93,
        "text": " basically",
        "before": " most of our release notes are",
        "after": " longer than they need to be. "
      }
    },
    {
      "id": "trim-ghost-3",
      "anchor": {
        "start": 163,
        "end": 222,
        "text": ", which is whether the update changes anything they rely on",
        "before": "open them to answer one question",
        "after": ", and they leave as soon as they"
      }
    },
    {
      "id": "trim-ghost-4",
      "anchor": {
        "start": 271,
        "end": 327,
        "text": " Every extra paragraph makes that answer harder to find.",
        "before": "as soon as they have the answer.",
        "after": "\n\nThe draft for the last release"
      }
    },
    {
      "id": "trim-ghost-5",
      "anchor": {
        "start": 442,
        "end": 473,
        "text": " (which nobody had asked about)",
        "before": "about the history of the project",
        "after": " before it reached the first "
      }
    },
    {
      "id": "trim-ghost-6",
      "anchor": {
        "start": 509,
        "end": 649,
        "text": " It then described the new search index in detail, really quite a lot of detail, although only a handful of users ever configure it by hand.",
        "before": " it reached the first change.",
        "after": " The breaking change to the "
      }
    },
    {
      "id": "trim-ghost-7",
      "anchor": {
        "start": 721,
        "end": 730,
        "text": " actually",
        "before": " file, the one thing that could",
        "after": " stop a deployment, appeared "
      }
    },
    {
      "id": "trim-ghost-8",
      "anchor": {
        "start": 813,
        "end": 821,
        "text": "Perhaps ",
        "before": " half of a long sentence.\n\n",
        "after": "the habit comes from how the "
      }
    },
    {
      "id": "trim-ghost-9",
      "anchor": {
        "start": 1132,
        "end": 1197,
        "text": " It is honestly not anyone's fault, and it is fairly easy to fix.",
        "before": " order that matters to a reader.",
        "after": "\n\nWe could start with a simple "
      }
    },
    {
      "id": "trim-ghost-10",
      "anchor": {
        "start": 1354,
        "end": 1469,
        "text": " If the answer is \"nothing\", the paragraph can simply say so — readers will be grateful for the time it saves them.",
        "before": " and it should say nothing else.",
        "after": " Everything that follows is "
      }
    },
    {
      "id": "trim-ghost-11",
      "anchor": {
        "start": 1921,
        "end": 1997,
        "text": ", which makes readers wonder whether there are really three separate changes",
        "before": " with slightly different wording",
        "after": ".\n\nIt would also be worth "
      }
    }
  ]
}
```
