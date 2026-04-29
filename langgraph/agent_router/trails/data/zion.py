_PARK_SAFETY = [
    "Check current conditions before hiking.",
    "Flash floods can affect canyon and river routes.",
    "Summer heat can be dangerous; carry extra water.",
    "Most wilderness trails do not allow pets. Pa'rus Trail is the main pet-friendly exception.",
    "Angels Landing requires a permit past Scout Lookout.",
]

# ---------------------------------------------------------------------------
# Top-level overview (no direct routes — points users to regions)
# ---------------------------------------------------------------------------
ZION_OVERVIEW = {
    "id": "zion-national-park",
    "name": "Zion National Park",
    "park": "Zion National Park",
    "state": "Utah",
    "aliases": [
        "zion",
        "zion np",
        "zion national park",
        "zion park",
    ],
    "safety": _PARK_SAFETY,
    "nodes": {},
    "routes": [],
    "sms_overview": (
        "Zion NP areas:\n"
        "1 Zion Canyon (main canyon/shuttle)\n"
        "2 East Rim (overlooks, Obs Point)\n"
        "3 SW Desert (Chinle, Coalpits)\n"
        "4 Kolob Canyons (wilderness)\n"
        "Ask about a specific area for routes."
    ),
    "ascii_map": (
        "Zion NP\n"
        "├ Zion Canyon (main)\n"
        "├ East Rim (east entrance)\n"
        "├ SW Desert (Rockville area)\n"
        "└ Kolob Canyons (NW corner)"
    ),
}

# ---------------------------------------------------------------------------
# Zion Canyon
# ---------------------------------------------------------------------------
ZION_CANYON = {
    "id": "zion-canyon",
    "name": "Zion Canyon",
    "park": "Zion National Park",
    "state": "Utah",
    "aliases": [
        "zion canyon",
        "angels landing",
        "narrows",
        "the narrows",
        "emerald pools",
        "scout lookout",
        "riverside walk",
        "parus trail",
        "pa'rus trail",
        "watchman trail",
        "zion shuttle",
    ],
    "safety": _PARK_SAFETY + [
        "Most Zion Canyon hikes are accessed by shuttle March-November.",
        "Check closures before starting.",
    ],
    "nodes": {
        "VC": {"name": "Visitor Center"},
        "CJ": {"name": "Canyon Junction"},
        "ZL": {"name": "Zion Lodge"},
        "GT": {"name": "The Grotto"},
        "BB": {"name": "Big Bend"},
        "TS": {"name": "Temple of Sinawava"},
        "PR": {"name": "Pa'rus Trail"},
        "RW": {"name": "Riverside Walk"},
        "NR": {"name": "The Narrows"},
        "EP": {"name": "Emerald Pools"},
        "KY": {"name": "Kayenta Trail"},
        "WR": {"name": "West Rim Trail"},
        "SL": {"name": "Scout Lookout"},
        "AL": {"name": "Angels Landing"},
        "WT": {"name": "Watchman Trail"},
    },
    "routes": [
        {
            "id": "parus",
            "label": "Pa'rus Trail",
            "route_type": "out-and-back / connector",
            "path": ["VC", "PR", "CJ"],
            "distance_miles": 3.5,
            "difficulty": "easy",
            "estimated_time": None,
            "best_for": ["easy walk", "bikes", "pets allowed", "accessibility"],
            "avoid_if": [],
            "summary": "Paved trail following the Virgin River from the Visitor Center toward Canyon Junction. Pet and bike friendly.",
        },
        {
            "id": "riverside-walk",
            "label": "Riverside Walk",
            "route_type": "out-and-back",
            "path": ["TS", "RW", "TS"],
            "distance_miles": 2.2,
            "difficulty": "easy",
            "estimated_time": None,
            "best_for": ["easy canyon walk", "start of Narrows"],
            "avoid_if": [],
            "summary": "Paved walk from Temple of Sinawava along the Virgin River. Gateway to the Narrows.",
        },
        {
            "id": "emerald-pools",
            "label": "Emerald Pools",
            "route_type": "trail-system",
            "path": ["ZL", "EP", "ZL"],
            "distance_note": "varies by pool / route",
            "difficulty": "easy / moderate",
            "estimated_time": None,
            "best_for": ["classic Zion stop", "short scenic hike"],
            "avoid_if": [],
            "summary": "Trail system from Zion Lodge / Kayenta area to lower, middle, and upper pools.",
        },
        {
            "id": "watchman",
            "label": "Watchman Trail",
            "route_type": "out-and-back",
            "path": ["VC", "WT", "VC"],
            "distance_miles": 3.3,
            "difficulty": "moderate",
            "estimated_time": None,
            "best_for": ["views near visitor center", "no shuttle needed"],
            "avoid_if": [],
            "summary": "Moderate hike from near the Visitor Center with views over lower Zion Canyon.",
        },
        {
            "id": "scout-lookout",
            "label": "Scout Lookout",
            "route_type": "out-and-back",
            "path": ["GT", "WR", "SL", "WR", "GT"],
            "distance_miles": 3.6,
            "difficulty": "hard",
            "estimated_time": None,
            "best_for": ["Angels Landing views without chain section"],
            "avoid_if": ["extreme heat", "ice", "poor footwear"],
            "summary": "Hard climb from The Grotto via West Rim Trail to Scout Lookout. Good view without the chain section.",
        },
        {
            "id": "angels-landing",
            "label": "Angels Landing",
            "route_type": "out-and-back",
            "path": ["GT", "WR", "SL", "AL", "SL", "WR", "GT"],
            "distance_miles": 5.4,
            "difficulty": "very hard",
            "estimated_time": None,
            "best_for": ["experienced hikers with permit", "iconic views"],
            "avoid_if": ["fear of heights", "ice", "storms", "high wind"],
            "summary": "Permit route beyond Scout Lookout with chains and major exposure. One of Zion's most iconic hikes.",
            "warnings": ["permit required past Scout Lookout", "chains", "exposure", "steep drop-offs"],
        },
        {
            "id": "narrows-bottom-up",
            "label": "The Narrows (bottom-up)",
            "route_type": "river out-and-back",
            "path": ["TS", "RW", "NR", "RW", "TS"],
            "distance_note": "turn around anytime; permit needed beyond Big Springs",
            "difficulty": "moderate / hard",
            "estimated_time": None,
            "best_for": ["river hike", "hot weather if conditions are safe"],
            "avoid_if": ["flash flood risk", "high flow", "cold water", "thunderstorms"],
            "summary": "River hike starting after Riverside Walk. Turn around any time. Check flash flood forecast and river flow before going.",
            "warnings": ["flash floods", "walking in water", "slippery rocks"],
        },
    ],
    "sms_overview": (
        "Zion Canyon:\n"
        "1 Pa'rus 3.5mi easy\n"
        "2 Riverside Walk 2.2mi easy\n"
        "3 Emerald Pools varies\n"
        "4 Watchman 3.3mi mod\n"
        "5 Scout Lookout 3.6mi hard\n"
        "6 Angels Landing 5.4mi permit\n"
        "7 Narrows varies\n"
        "Reply route name or number for details."
    ),
    "ascii_map": (
        "Zion Canyon  N↑\n"
        "Temple of Sinawava\n"
        " └ Riverside Walk → Narrows\n"
        "Big Bend\n"
        " └ Angels Landing / Scout\n"
        "The Grotto\n"
        " ├ Kayenta Trail\n"
        " └ West Rim Trail\n"
        "Zion Lodge\n"
        " └ Emerald Pools\n"
        "Visitor Center\n"
        " ├ Pa'rus Trail\n"
        " └ Watchman Trail"
    ),
}

# ---------------------------------------------------------------------------
# East Rim / East Side
# ---------------------------------------------------------------------------
EAST_RIM = {
    "id": "east-rim",
    "name": "East Rim",
    "park": "Zion National Park",
    "state": "Utah",
    "aliases": [
        "east rim",
        "east side",
        "east rim zion",
        "canyon overlook",
        "observation point",
        "east mesa",
        "cable mountain",
        "deertrap mountain",
    ],
    "safety": _PARK_SAFETY + [
        "East Rim Trail does not connect to Zion Canyon due to a rockfall closure.",
        "East Mesa road may require 4WD or high clearance after rain.",
    ],
    "nodes": {},
    "routes": [
        {
            "id": "canyon-overlook",
            "label": "Canyon Overlook Trail",
            "route_type": "out-and-back",
            "path": [],
            "distance_miles": 1.0,
            "distance_note": "1.0 mi round trip, 163 ft gain",
            "difficulty": "moderate",
            "estimated_time": None,
            "best_for": ["quick viewpoint", "east entrance area"],
            "avoid_if": [],
            "summary": "Short but rewarding overlook hike just past the Zion-Mt Carmel Tunnel. Watch for drop-offs.",
            "warnings": ["drop-offs", "rocky/uneven", "limited parking"],
        },
        {
            "id": "east-rim",
            "label": "East Rim Trail",
            "route_type": "out-and-back / connector",
            "path": [],
            "distance_note": "5.9 mi one-way to Stave Spring; 10.6 mi one-way to Observation Point",
            "difficulty": "hard",
            "estimated_time": None,
            "best_for": ["high-country solitude", "rim views"],
            "avoid_if": [],
            "summary": "Long high-elevation trail from the east entrance. Does NOT connect to Zion Canyon due to rockfall closure.",
            "warnings": ["no connection to Zion Canyon"],
        },
        {
            "id": "east-mesa-observation-point",
            "label": "East Mesa Trail to Observation Point",
            "route_type": "out-and-back",
            "path": [],
            "distance_miles": 6.8,
            "distance_note": "6.8 mi round trip",
            "difficulty": "moderate",
            "estimated_time": None,
            "best_for": ["Observation Point without canyon climb", "high-clearance vehicle"],
            "avoid_if": ["wet roads", "no high-clearance vehicle"],
            "summary": "Best route to Observation Point. Access road can be muddy or require 4WD after rain.",
            "warnings": ["4WD/high-clearance road access", "muddy after rain", "private property parking nearby"],
        },
        {
            "id": "stave-spring",
            "label": "Stave Spring Trail",
            "route_type": "access trail",
            "path": [],
            "distance_note": "0.3 mi one-way",
            "difficulty": "easy",
            "estimated_time": None,
            "best_for": ["East Rim access junction"],
            "avoid_if": [],
            "summary": "Short access trail connecting to the East Rim near Stave Spring.",
        },
        {
            "id": "deertrap",
            "label": "Deertrap Mountain Trail",
            "route_type": "out-and-back",
            "path": [],
            "distance_note": "9.8 mi RT from Stave Spring; 20.4 mi RT from East Rim TH",
            "difficulty": "hard",
            "estimated_time": None,
            "best_for": ["long rim views", "experienced hikers"],
            "avoid_if": ["limited water"],
            "summary": "Long rim hike with expansive views. Distance depends on starting point.",
        },
        {
            "id": "cable-mountain",
            "label": "Cable Mountain Trail",
            "route_type": "out-and-back",
            "path": [],
            "distance_note": "7 mi RT from Stave Spring; 17.6 mi RT from East Entrance",
            "difficulty": "hard",
            "estimated_time": None,
            "best_for": ["rim views", "historic cableworks"],
            "avoid_if": ["limited water"],
            "summary": "Rim hike to historic cable works used to lower lumber into Zion Canyon.",
        },
    ],
    "sms_overview": (
        "East Rim (Zion NP):\n"
        "1 Canyon Overlook 1.0mi mod\n"
        "2 East Rim Trail 5.9-10.6mi hard\n"
        "3 East Mesa → Obs Pt 6.8mi mod\n"
        "4 Stave Spring 0.3mi access\n"
        "5 Deertrap Mtn 9.8-20.4mi hard\n"
        "6 Cable Mountain 7-17.6mi hard\n"
        "Reply route name or number."
    ),
    "ascii_map": (
        "East Rim (Zion)\n"
        "East Entrance\n"
        " ├ Canyon Overlook\n"
        " └ East Rim Trail\n"
        "    └ Stave Spring\n"
        "       ├ Deertrap Mtn\n"
        "       │  └ Cable Mtn\n"
        "       └ Observation Pt\n"
        "East Mesa TH → Observation Pt"
    ),
}

# ---------------------------------------------------------------------------
# Southwest Desert
# ---------------------------------------------------------------------------
SOUTHWEST_DESERT = {
    "id": "southwest-desert",
    "name": "Southwest Desert",
    "park": "Zion National Park",
    "state": "Utah",
    "aliases": [
        "southwest desert",
        "sw desert",
        "zion southwest",
        "chinle trail",
        "chinle",
        "coalpits wash",
        "coalpits",
    ],
    "safety": _PARK_SAFETY + [
        "Extremely hot and exposed in summer; avoid midday heat.",
        "Wash routes can flood with no warning.",
        "Trails are less marked — bring a map.",
    ],
    "nodes": {},
    "routes": [
        {
            "id": "chinle",
            "label": "Chinle Trail",
            "route_type": "one-way / out-and-back",
            "path": [],
            "distance_note": "8.2 mi one-way to Coalpits Spring; 11.7 mi one-way to Coalpits Wash TH",
            "difficulty": "hard",
            "estimated_time": "4-7 hr one-way",
            "best_for": ["desert solitude", "point-to-point with shuttle"],
            "avoid_if": ["summer midday", "after heavy rain"],
            "summary": "Long desert route with little shade. Muddy and slippery when wet.",
            "warnings": ["little shade", "extreme summer heat", "muddy when wet"],
        },
        {
            "id": "coalpits-wash",
            "label": "Coalpits Wash Trail",
            "route_type": "one-way / wash route",
            "path": [],
            "distance_note": "3.6 mi one-way to Coalpits Spring; 11.7 mi one-way to Chinle TH",
            "difficulty": "moderate / hard",
            "estimated_time": "2 hr one-way to Coalpits Spring",
            "best_for": ["desert wash hiking", "shorter desert option"],
            "avoid_if": ["summer midday", "flash flood risk"],
            "summary": "Desert wash route heading toward Coalpits Spring. Hot and exposed.",
            "warnings": ["little shade", "extreme summer heat", "wash route"],
        },
    ],
    "sms_overview": (
        "SW Desert (Zion NP):\n"
        "1 Chinle Trail 8.2-11.7mi hard\n"
        "2 Coalpits Wash 3.6mi+ mod/hard\n"
        "Hot, exposed, less marked.\n"
        "Reply route name or number."
    ),
    "ascii_map": (
        "SW Desert (Zion)\n"
        "Chinle TH\n"
        " └ Chinle Trail\n"
        "    └ Coalpits Spring\n"
        "       └ Coalpits Wash TH\n"
        "Coalpits TH\n"
        " └ Coalpits Wash → Chinle"
    ),
}

# ---------------------------------------------------------------------------
# Kolob Canyons
# ---------------------------------------------------------------------------
KOLOB_CANYONS = {
    "id": "kolob-canyons",
    "name": "Kolob Canyons",
    "park": "Zion National Park",
    "state": "Utah",
    "aliases": [
        "kolob",
        "kolob canyons",
        "kolob arch",
        "la verkin creek",
        "taylor creek",
        "hop valley",
        "timber creek",
    ],
    "safety": _PARK_SAFETY + [
        "Kolob Canyons has a separate entrance fee/pass.",
        "Overnight stays require a wilderness permit.",
    ],
    "nodes": {},
    "routes": [
        {
            "id": "timber-creek-overlook",
            "label": "Timber Creek Overlook",
            "route_type": "out-and-back",
            "path": [],
            "distance_note": "1.0 mi round trip",
            "difficulty": "easy",
            "estimated_time": "30-45 min",
            "best_for": ["quick overlook", "families"],
            "avoid_if": [],
            "summary": "Short hike at the end of the Kolob Canyons road with panoramic red-rock views.",
        },
        {
            "id": "taylor-creek",
            "label": "Taylor Creek Trail",
            "route_type": "out-and-back",
            "path": [],
            "distance_note": "5.0 mi round trip",
            "difficulty": "moderate",
            "estimated_time": "2-3 hr",
            "best_for": ["classic Kolob canyon hike", "Double Arch Alcove"],
            "avoid_if": [],
            "summary": "Follows Middle Fork of Taylor Creek through a narrow canyon to Double Arch Alcove.",
        },
        {
            "id": "la-verkin-creek",
            "label": "La Verkin Creek Trail / Kolob Arch",
            "route_type": "out-and-back / backpacking",
            "path": [],
            "distance_note": "14 mi round trip to Kolob Arch",
            "difficulty": "hard",
            "estimated_time": "full day or overnight",
            "best_for": ["experienced hikers", "Kolob Arch — one of world's largest"],
            "avoid_if": ["limited water", "no permit for overnight"],
            "summary": "Long wilderness route to Kolob Arch from Lee Pass. Permit required for overnight camping.",
            "warnings": ["overnight permit required", "long distance", "limited water sources"],
        },
        {
            "id": "hop-valley",
            "label": "Hop Valley Trail",
            "route_type": "out-and-back / connector",
            "path": [],
            "distance_note": "13 mi round trip",
            "difficulty": "hard",
            "estimated_time": "full day or overnight",
            "best_for": ["wilderness solitude", "Zion Narrows connector"],
            "avoid_if": ["wet conditions", "no permit for overnight"],
            "summary": "Long wilderness route through open valley with creek crossings. Can connect to the Narrows via Wildcat Canyon.",
            "warnings": ["overnight permit required", "creek crossings"],
        },
    ],
    "sms_overview": (
        "Kolob Canyons (Zion NP):\n"
        "1 Timber Creek Overlook 1.0mi easy\n"
        "2 Taylor Creek 5.0mi mod\n"
        "3 La Verkin Creek / Kolob Arch 14mi hard\n"
        "4 Hop Valley 13mi hard\n"
        "Separate entrance. Overnight = permit.\n"
        "Reply route name or number."
    ),
    "ascii_map": (
        "Kolob Canyons (Zion)\n"
        "Visitor Ctr / Scenic Rd\n"
        " ├ Timber Creek Overlook\n"
        " ├ Taylor Creek\n"
        " ├ Lee Pass\n"
        " │  └ La Verkin Creek\n"
        " │     └ Kolob Arch\n"
        " └ Hop Valley"
    ),
}
