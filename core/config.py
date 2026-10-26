"""إعدادات عامة. لإضافة منصة جديدة (مثلاً Hunger Station): ضيفها هنا + اكتب parser لها في parsers.py"""

# المنصات: parser = اسم الـ parser الموجود في parsers.PARSERS (None = لسه مفيش parser)
PLATFORMS = {
    "Keeta": {"parser": "keeta"},
    
    "Hunger Station": {"parser": None},   # جاهزة في السيستم، هتتفعل لما نضيف parser لها
}

DEFAULT_CITIES = ["Riyadh"]

# فترات الشيفت زي ما بتيجي في إكسبورت Keeta
SLOTS = ["00:00-03:00", "03:00-08:00", "08:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]
SLOT_COLS = ["shift_" + s.replace(":", "").replace("-", "_") for s in SLOTS]   # shift_0000_0300 ...
