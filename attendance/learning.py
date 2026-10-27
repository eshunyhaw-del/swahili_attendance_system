"""Learn a Skill: the course catalogue.

Courses are plain data (not database rows) so adding one is a code change that is
reviewed and tested. Only each student's progress lives in the database.
"""

VIDEO_EMBED = "https://www.youtube-nocookie.com/embed/{id}"


def _mmss(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def _lesson(key, title, start, summary):
    return {'key': key, 'title': title, 'start': start, 'time': _mmss(start), 'summary': summary}


DESIGN_WEBSITES_WITH_AI = {
    'slug': 'design-websites-with-ai',
    'title': 'Learn how to design websites with AI',
    'summary': (
        "Use Claude or ChatGPT to design a real website. You find inspiration, record it as a "
        "reference, give the AI a design system, fonts and your own images, then refine the "
        "result until it looks like a professional business site."
    ),
    'video_id': 'SpRVakDblFE',
    'level': 'Beginner friendly',
    'duration': 'About 50 minutes',
    'format': 'Video lesson with chapters',
    'outcomes': [
        "Find websites worth learning from, and say exactly why they work",
        "Record a website as a reference you can hand to an AI",
        "Get ChatGPT or Claude to describe a site's feeling, motion and parallax scrolling",
        "Find the font a website uses and download free fonts safely",
        "Understand what a design system is and have the AI create one for your brand",
        "Organise a project folder with fonts and images, then brief the AI properly",
        "Preview your site on your own computer and improve it with follow-up prompts",
        "Check contrast and accessibility, and make it feel like a real business website",
    ],
    'prerequisites': [
        "A computer with an internet connection",
        "A free ChatGPT or Claude account",
        "A few images for your website, or free ones from Pexels or Unsplash",
        "A screen recorder (Windows has one built in, and the video shows other free options)",
    ],
    'tools': [
        {'name': 'details.so', 'url': 'https://details.so', 'note': 'Website inspiration collection'},
        {'name': 'Awwwards', 'url': 'https://www.awwwards.com', 'note': 'Award-winning website designs'},
        {'name': 'Google Fonts', 'url': 'https://fonts.google.com', 'note': 'Free fonts you can use in your projects'},
        {'name': 'OBS Studio', 'url': 'https://obsproject.com', 'note': 'Free screen recording'},
        {'name': 'Pexels', 'url': 'https://www.pexels.com', 'note': 'Free photos'},
        {'name': 'Unsplash', 'url': 'https://unsplash.com', 'note': 'Free photos'},
        {'name': 'ChatGPT', 'url': 'https://chatgpt.com', 'note': 'AI assistant'},
        {'name': 'Claude', 'url': 'https://claude.ai', 'note': 'AI assistant'},
    ],
    'sections': [
        ('Get inspired', [
            _lesson('intro', 'What we are building', 0, 'The technique: give an AI a real website as a reference.'),
            _lesson('inspiration', 'Find an inspiring website', 22, 'Browse details.so and pick a site you love.'),
        ]),
        ('Record your reference', [
            _lesson('record-screen', 'Record the site with a screen recorder', 77, 'Capture the site you chose, including how it moves.'),
            _lesson('record-other', 'Other ways to record your screen', 174, 'The Windows shortcut, OBS Studio, and why Google Meet will not work.'),
            _lesson('reference', 'Give the recording to the AI', 388, 'Ask ChatGPT to describe the emotions and motion in the site.'),
        ]),
        ('Learn from other sites', [
            _lesson('more-inspiration', 'More places to find inspiration', 534, 'Awwwards and other collections, and how to use them.'),
            _lesson('analysis', 'Read the AI analysis', 671, 'Parallax scrolling and scroll-triggered transitions explained.'),
            _lesson('industry', 'Choose what you are building', 736, 'Pick an industry and tell the AI about your business.'),
        ]),
        ('Fonts and design system', [
            _lesson('fonts', 'Find the font a website uses', 840, 'Right-click, Inspect, and read the font name.'),
            _lesson('folder', 'Set up your project folder', 943, 'A folder with assets, fonts and images.'),
            _lesson('download-font', 'Download a free font', 994, 'Use Google Fonts, and watch out for fonts that need a licence.'),
            _lesson('design-system', 'What is a design system?', 1152, 'Why big brands always look consistent.'),
            _lesson('ai-design-system', 'Ask the AI for your design system', 1415, 'Get a clean, minimal set of colours and rules.'),
            _lesson('images', 'Add your images', 1601, 'Put your photos in the project folder for the AI to use.'),
        ]),
        ('Build with AI', [
            _lesson('build', 'Brief the AI and let it build', 1745, 'Open the folder in the ChatGPT desktop app and answer its questions.'),
            _lesson('limit', 'When you hit a usage limit', 1987, 'Switch tools and keep going.'),
            _lesson('local', 'Preview the site on your computer', 2049, 'Open the local version, with or without coding tools.'),
            _lesson('animation', 'Give the AI your reference video', 2215, 'Ask Claude to copy the motion from your recording.'),
        ]),
        ('Polish and launch', [
            _lesson('iterate', 'Review and improve', 2403, 'Ask for smoother scrolling and more sections.'),
            _lesson('real', 'Make it feel like a real business site', 2543, 'Proper page names, a WhatsApp button, and no AI giveaways.'),
            _lesson('accessibility', 'Check accessibility and contrast', 2722, 'Make sure every word is easy to read.'),
            _lesson('final', 'The final result, and mobile', 2811, 'Review the finished site on a phone.'),
            _lesson('next', 'What comes next: immersive websites', 2852, 'A preview of the next lesson.'),
        ]),
    ],
}

COURSES = [DESIGN_WEBSITES_WITH_AI]
COURSES_BY_SLUG = {c['slug']: c for c in COURSES}

COMING_SOON = [
    {'title': 'How to Use a Computer', 'blurb': 'Files, folders, typing and the basics every student needs.'},
    {'title': 'Learn Google Workspace for Beginners', 'blurb': 'Docs, Sheets, Slides, Drive and Meet.'},
    {'title': 'How to Use Claude and ChatGPT for Everyday Life', 'blurb': 'Practical ways to get help from AI.'},
    {'title': 'Personal Development: CV Writing', 'blurb': 'Write a CV that gets read.'},
    {'title': 'Become a Web Developer', 'blurb': 'HTML, CSS and JavaScript from the start.'},
    {'title': 'Become a Digital Marketer', 'blurb': 'Reach customers and grow a brand online.'},
    {'title': 'Become a Software Developer', 'blurb': 'Learn to build software step by step.'},
    {'title': 'How to Navigate the Corporate World', 'blurb': 'Start your career with confidence.'},
    {'title': 'Microsoft 365 for Beginners', 'blurb': 'Word, Excel, PowerPoint and Teams.'},
    {'title': 'After University, What Is Next?', 'blurb': 'Plan your next step after graduation.'},
]


def lesson_keys(course):
    return [lesson['key'] for _, lessons in course['sections'] for lesson in lessons]


def lesson_count(course):
    return len(lesson_keys(course))


def watch_url(course):
    return f"https://www.youtube.com/watch?v={course['video_id']}"


def embed_url(course, start=None):
    url = VIDEO_EMBED.format(id=course['video_id']) + "?rel=0"
    if start:
        url += f"&start={int(start)}&autoplay=1"
    return url
