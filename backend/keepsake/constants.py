"""Shared constants: item types, colour tones, sort options."""

# key -> display metadata. "tone" maps to a .tone-* class in the stylesheet.
TYPES = {
    "memory": {
        "label": "Memory",
        "plural": "Memories",
        "emoji": "💭",
        "tone": "rose",
        "hint": "A moment, a story, a feeling worth keeping.",
    },
    "photo": {
        "label": "Photo",
        "plural": "Photos",
        "emoji": "📷",
        "tone": "sky",
        "hint": "A picture, pinned up with its story.",
    },
    "note": {
        "label": "Note",
        "plural": "Notes",
        "emoji": "📝",
        "tone": "sun",
        "hint": "Ideas, lists, recipes, little reminders.",
    },
    "document": {
        "label": "Document",
        "plural": "Documents",
        "emoji": "📄",
        "tone": "grape",
        "hint": "PDFs, letters, certificates, important papers.",
    },
    "link": {
        "label": "Link",
        "plural": "Links",
        "emoji": "🔗",
        "tone": "mint",
        "hint": "A page on the web you never want to lose.",
    },
}

COLLECTION_TONES = ["coral", "sun", "mint", "sky", "grape", "rose", "peach", "teal"]

COLLECTION_EMOJIS = [
    "📚", "🌍", "🎒", "🎂", "💌", "🏡", "🎨", "🌸",
    "🐶", "🍰", "🎵", "⭐", "👨‍👩‍👧", "🎓", "💼", "🌈",
]

# key -> (label, ORDER BY clause). Only these strings ever reach the SQL.
SORTS = {
    "date_desc": ("Newest date first", "i.item_date DESC, i.id DESC"),
    "date_asc": ("Oldest date first", "i.item_date ASC, i.id ASC"),
    "added_desc": ("Recently added", "i.created_at DESC, i.id DESC"),
    "title_asc": ("Title A to Z", "i.title ASC, i.id ASC"),
    "title_desc": ("Title Z to A", "i.title DESC, i.id DESC"),
}

PER_PAGE = 12
