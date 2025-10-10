"""
Sermon tag configuration.

This module defines all available tags for categorizing sermon messages.
Tags are organized by topic/theme to enable better organization and discovery.

To add new tags:
1. Add the tag name to the appropriate category list below
2. The tag will be automatically available on the next run (no other changes needed)

Tag naming conventions:
- Use PascalCase (e.g., "Marriage", "FinancialStewardship")
- Be descriptive but concise
- Avoid abbreviations unless widely understood
"""

# Relationships & Family
RELATIONSHIPS_FAMILY = [
    "Marriage",           # Topics related to marriage, dating, and romantic relationships
    "Family",             # Topics related to parenting, children, and family dynamics
    "Friendship",         # Topics related to friendships and community relationships
    "Singleness",         # Topics related to singleness and navigating life as a single person
]

# Financial & Stewardship
FINANCIAL = [
    "FinancialStewardship",  # Topics related to money management, budgeting, and financial wisdom
    "Generosity",            # Topics related to generosity, tithing, and giving
]

# Theological Foundations
THEOLOGICAL = [
    "NatureOfGod",        # Topics related to the nature and character of God
    "Trinity",            # Topics related to the Trinity (Father, Son, Holy Spirit)
    "Salvation",          # Topics related to salvation, grace, and redemption
    "Resurrection",       # Topics related to the resurrection of Jesus and believers
    "HolySpirit",         # Topics related to the Holy Spirit and spiritual gifts
    "Church",             # Topics related to the church, ecclesiology, and the body of Christ
    "EndTimes",           # Topics related to end times, eschatology, and the return of Christ
    "SinAndRepentance",   # Topics related to sin, repentance, and forgiveness
    "Sanctification",     # Topics related to sanctification and becoming more Christ-like
    "Covenant",           # Topics related to biblical covenants (Abrahamic, Mosaic, Davidic, New Covenant)
    "Apologetics",        # Topics related to defending the Christian faith and answering objections
]

# Spiritual Disciplines
SPIRITUAL_DISCIPLINES = [
    "Prayer",             # Topics related to prayer and intercession
    "Fasting",            # Topics related to fasting and spiritual discipline
    "Worship",            # Topics related to worship and praise
    "BibleStudy",         # Topics related to Bible study and Scripture engagement
    "Meditation",         # Topics related to meditation and contemplation
    "Service",            # Topics related to service and ministry to others
    "Praise",             # Topics related to praise and praising God
]

# Sacraments & Ordinances
SACRAMENTS = [
    "Baptism",            # Topics related to baptism and its significance
    "Communion",          # Topics related to communion, the Lord's Supper, or Eucharist
]

# Life Stages & Transitions
LIFE_STAGES = [
    "Youth",              # Topics related to youth and young adult life
    "Aging",              # Topics related to aging, retirement, and senior life
    "GriefAndLoss",       # Topics related to grief, loss, and mourning
    "LifeTransitions",    # Topics related to major life transitions and changes
]

# Social Issues & Justice
SOCIAL_ISSUES = [
    "SocialJustice",      # Topics related to social justice, equity, and righteousness
    "RacialReconciliation",  # Topics related to racial reconciliation and unity
    "Poverty",            # Topics related to poverty, homelessness, and economic justice
    "Creation",           # Topics related to caring for creation and environmental stewardship
    "Politics",           # Topics related to politics, government, and civic engagement
]

# Personal Growth & Character
PERSONAL_GROWTH = [
    "Identity",           # Topics related to identity in Christ and self-worth
    "Purpose",            # Topics related to purpose, calling, and vocation
    "Courage",            # Topics related to courage, bravery, and overcoming fear
    "Hope",               # Topics related to hope and optimism
    "Love",               # Topics related to love and compassion
    "Joy",                # Topics related to joy and contentment
    "Peace",              # Topics related to peace and rest
    "Patience",           # Topics related to patience and perseverance
    "Humility",           # Topics related to humility and servanthood
    "Wisdom",             # Topics related to wisdom and discernment
    "Integrity",          # Topics related to integrity and character
    "Forgiveness",        # Topics related to forgiveness and reconciliation
    "Gratitude",          # Topics related to gratitude and thankfulness
    "Trust",              # Topics related to trust and trusting God in all circumstances
    "Obedience",          # Topics related to obedience and following God's commands
    "Contentment",        # Topics related to contentment and finding satisfaction in God
    "Pride",              # Topics related to pride and dealing with arrogance
    "Fear",               # Topics related to fear and overcoming fear with faith
    "Anger",              # Topics related to anger and managing it biblically
]

# Challenges & Struggles
CHALLENGES = [
    "Suffering",          # Topics related to suffering, trials, and hardship
    "Doubt",              # Topics related to doubt and questions of faith
    "Anxiety",            # Topics related to anxiety, worry, and mental health
    "Depression",         # Topics related to depression and emotional struggles
    "Addiction",          # Topics related to addiction and recovery
    "Temptation",         # Topics related to temptation and spiritual warfare
    "SpiritualWarfare",   # Topics related to spiritual warfare and battling spiritual forces
    "Persecution",        # Topics related to persecution and enduring hardship for faith
]

# Eternal & Supernatural
ETERNAL = [
    "Heaven",             # Topics related to heaven and eternal life
    "Hell",               # Topics related to hell and eternal judgment
]

# Mission & Evangelism
MISSION = [
    "Evangelism",         # Topics related to evangelism and sharing faith
    "Missions",           # Topics related to missions and global outreach
    "Discipleship",       # Topics related to discipleship and spiritual growth
    "Leadership",         # Topics related to leadership and influence
    "Witnessing",         # Topics related to personal evangelism, witnessing, and sharing testimony
]

# Biblical Studies
BIBLICAL_STUDIES = [
    "Parables",           # Topics related to the parables of Jesus
    "SermonOnTheMount",   # Topics related to the Sermon on the Mount (Matthew 5-7)
    "FruitOfTheSpirit",   # Topics related to the Fruit of the Spirit (Galatians 5:22-23)
    "ArmorOfGod",         # Topics related to the Armor of God (Ephesians 6)
    "Prophets",           # Topics related to Old Testament prophets and their messages
]

# Biblical Book Studies
BOOK_STUDIES = [
    "Genesis",            # Sermon series studying the book of Genesis
    "Exodus",             # Sermon series studying the book of Exodus
    "Psalms",             # Sermon series studying the book of Psalms
    "Proverbs",           # Sermon series studying the book of Proverbs
    "Gospels",            # Sermon series studying the Gospels (Matthew, Mark, Luke, John)
    "Acts",               # Sermon series studying the book of Acts
    "Romans",             # Sermon series studying the book of Romans
    "PaulineEpistles",    # Sermon series studying other Pauline epistles
    "Revelation",         # Sermon series studying Revelation
    "OldTestament",       # General Old Testament book studies not otherwise categorized
    "NewTestament",       # General New Testament book studies not otherwise categorized
]

# Seasonal & Liturgical
SEASONAL = [
    "Advent",             # Topics related to Advent season
    "Christmas",          # Topics related to Christmas season
    "Lent",               # Topics related to Lent season
    "Easter",             # Topics related to Easter season
    "Pentecost",          # Topics related to Pentecost
]

# Work & Vocation
WORK = [
    "Work",               # Topics related to work, career, and professional life
    "Rest",               # Topics related to rest, sabbath, and work-life balance
]

# Gender & Relationships
GENDER = [
    "BiblicalManhood",    # Topics related to biblical manhood and what it means to be a godly man
    "BiblicalWomanhood",  # Topics related to biblical womanhood and what it means to be a godly woman
    "SexualPurity",       # Topics related to sexual purity and biblical sexuality
]

# Other
OTHER = [
    "Miracles",           # Topics related to miracles and the supernatural
    "Prophecy",           # Topics related to prophecy and prophetic ministry
    "Healing",            # Topics related to healing and restoration
    "Community",          # Topics related to community and fellowship
    "Culture",            # Topics related to culture and cultural engagement
    "Technology",         # Topics related to technology and modern life
]

# Master list of all tags (automatically generated from categories above)
ALL_TAGS = (
    RELATIONSHIPS_FAMILY +
    FINANCIAL +
    THEOLOGICAL +
    SPIRITUAL_DISCIPLINES +
    SACRAMENTS +
    LIFE_STAGES +
    SOCIAL_ISSUES +
    PERSONAL_GROWTH +
    CHALLENGES +
    ETERNAL +
    MISSION +
    BIBLICAL_STUDIES +
    BOOK_STUDIES +
    SEASONAL +
    WORK +
    GENDER +
    OTHER
)


def get_all_tags():
    """
    Get the complete list of all available tags.
    
    Returns:
        List of all tag names
    """
    return ALL_TAGS


def get_tags_by_category():
    """
    Get tags organized by category.
    
    Returns:
        Dictionary mapping category names to lists of tags
    """
    return {
        "Relationships & Family": RELATIONSHIPS_FAMILY,
        "Financial & Stewardship": FINANCIAL,
        "Theological Foundations": THEOLOGICAL,
        "Spiritual Disciplines": SPIRITUAL_DISCIPLINES,
        "Sacraments & Ordinances": SACRAMENTS,
        "Life Stages & Transitions": LIFE_STAGES,
        "Social Issues & Justice": SOCIAL_ISSUES,
        "Personal Growth & Character": PERSONAL_GROWTH,
        "Challenges & Struggles": CHALLENGES,
        "Eternal & Supernatural": ETERNAL,
        "Mission & Evangelism": MISSION,
        "Biblical Studies": BIBLICAL_STUDIES,
        "Biblical Book Studies": BOOK_STUDIES,
        "Seasonal & Liturgical": SEASONAL,
        "Work & Vocation": WORK,
        "Gender & Relationships": GENDER,
        "Other": OTHER,
    }


def get_tag_count():
    """
    Get the total number of available tags.
    
    Returns:
        Integer count of tags
    """
    return len(ALL_TAGS)

