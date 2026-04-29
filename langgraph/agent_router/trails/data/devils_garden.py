DEVILS_GARDEN = {
    "id": "devils-garden",
    "name": "Devils Garden",
    "park": "Arches National Park",
    "state": "Utah",
    "aliases": [
        "devils garden",
        "devil's garden",
        "devils garden trail",
        "arches devils garden",
        "arches national park",
        "arches",
    ],
    "summary": (
        "A trail system in Arches with easy arches near the start "
        "and harder scrambling past Landscape Arch."
    ),
    "safety": [
        "Bring water; shade is limited.",
        "Do not climb or walk on arches.",
        "Primitive Trail is not recommended when wet or icy.",
        "Past Landscape Arch, expect scrambling, narrow ledges, and route-finding.",
    ],
    "nodes": {
        "TH": {"name": "Trailhead",       "note": "Main parking/start point."},
        "PT": {"name": "Pine Tree Arch",   "note": "Short side trail near the beginning."},
        "TU": {"name": "Tunnel Arch",      "note": "Short side trail near Pine Tree Arch."},
        "LA": {"name": "Landscape Arch",   "note": "Popular easier destination before the trail gets harder."},
        "NA": {"name": "Navajo Arch",      "note": "Optional side trail between Landscape and Double O."},
        "PA": {"name": "Partition Arch",   "note": "Optional side trail between Landscape and Double O."},
        "DO": {"name": "Double O Arch",    "note": "Harder route past Landscape with scrambling and ledges."},
        "DA": {"name": "Dark Angel",       "note": "Optional spur beyond Double O."},
        "PR": {"name": "Primitive Trail",  "note": "Most difficult segment; route finding, scrambling, drop-offs."},
        "PV": {"name": "Private Arch",     "note": "Optional spur off the Primitive Trail."},
    },
    "routes": [
        {
            "id": "landscape",
            "label": "Landscape Arch",
            "route_type": "out-and-back",
            "path": ["TH", "LA", "TH"],
            "distance_miles": 1.9,
            "difficulty": "easy",
            "estimated_time": "45-90 min",
            "best_for": ["short hike", "families", "limited time"],
            "avoid_if": [],
            "summary": "Best short option. Easy route to Landscape Arch and back.",
        },
        {
            "id": "pine-tunnel",
            "label": "Pine Tree + Tunnel Arches",
            "route_type": "side-spurs",
            "path": ["TH", "PT", "TH", "TU", "TH"],
            "distance_miles": 0.5,
            "distance_note": "+0.5 mi added to any route",
            "difficulty": "easy",
            "estimated_time": "20-40 min extra",
            "best_for": ["quick add-on", "easy arches"],
            "avoid_if": [],
            "summary": "Short side trails near the start, easy add-on.",
        },
        {
            "id": "double-o",
            "label": "Double O Arch",
            "route_type": "out-and-back",
            "path": ["TH", "LA", "DO", "LA", "TH"],
            "distance_miles": 4.1,
            "difficulty": "hard",
            "estimated_time": "2-3 hr",
            "best_for": ["strong hikers", "bigger views"],
            "avoid_if": ["fear of heights", "wet rock", "darkness"],
            "summary": "Harder route beyond Landscape Arch with scrambling, sandstone fins, and narrow ledges.",
        },
        {
            "id": "navajo-partition",
            "label": "Navajo + Partition Arches",
            "route_type": "side-spurs",
            "path": ["LA", "NA", "LA", "PA", "LA"],
            "distance_miles": 0.8,
            "distance_note": "+0.8 mi added from Landscape Arch",
            "difficulty": "moderate",
            "estimated_time": "30-60 min extra",
            "best_for": ["extra arches", "side trip"],
            "avoid_if": [],
            "summary": "Optional side trails between Landscape Arch and Double O Arch.",
        },
        {
            "id": "dark-angel",
            "label": "Dark Angel",
            "route_type": "out-and-back",
            "path": ["TH", "LA", "DO", "DA", "DO", "LA", "TH"],
            "distance_miles": 4.9,
            "difficulty": "hard",
            "estimated_time": "3-4 hr",
            "best_for": ["longer hike", "experienced hikers"],
            "avoid_if": ["heat", "low water", "late start"],
            "summary": "Longer out-and-back past Double O to Dark Angel spire.",
        },
        {
            "id": "primitive-loop",
            "label": "Primitive Loop",
            "route_type": "loop",
            "path": ["TH", "LA", "DO", "DA", "DO", "PR", "PV", "LA", "TH"],
            "distance_miles": 6.6,
            "difficulty": "very hard",
            "estimated_time": "4-6 hr",
            "best_for": ["experienced hikers", "route-finding practice"],
            "avoid_if": ["wet rock", "ice", "fear of heights", "late start", "low water"],
            "summary": (
                "Hard loop using the Primitive Trail. "
                "Expect route-finding, scrambling, and exposed areas."
            ),
        },
        {
            "id": "all-spurs",
            "label": "Full System — All Spurs",
            "route_type": "full-system",
            "path": ["TH", "PT", "TU", "LA", "NA", "PA", "DO", "DA", "PR", "PV", "TH"],
            "distance_miles": 7.9,
            "difficulty": "very hard",
            "estimated_time": "5-7 hr",
            "best_for": ["full day", "experienced hikers"],
            "avoid_if": ["heat", "wet rock", "low water", "late start"],
            "summary": "Full Devils Garden route including all major side trails.",
        },
    ],
    "sms_overview": (
        "Devils Garden - Arches NP:\n"
        "1 Landscape 1.9mi easy\n"
        "2 Pine/Tunnel +0.5 easy\n"
        "3 Double O 4.1mi hard\n"
        "4 Nav/Partition +0.8 mod\n"
        "5 Dark Angel 4.9mi hard\n"
        "6 Primitive Loop 6.6mi v.hard\n"
        "7 All Spurs 7.9mi v.hard\n"
        "Reply with route name or number for details."
    ),
    "ascii_map": (
        "Devils Garden\n"
        "TH\n"
        "├ Pine Tree / Tunnel +0.5\n"
        "└ Landscape Arch 1.9RT\n"
        "  ├ Navajo / Partition +0.8\n"
        "  └ Double O Arch 4.1RT\n"
        "    ├ Dark Angel 4.9RT\n"
        "    └ Primitive Loop 6.6RT"
    ),
}
