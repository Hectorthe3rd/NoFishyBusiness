"""
knowledge_base/seed.py

Creates the aquarium.db SQLite database schema and provides helper functions
for inserting and retrieving knowledge base records.

Schema:
    - kb_records: primary records table
    - kb_fts: FTS5 virtual table mirroring kb_records for full-text search
    - kb_ai / kb_ad: triggers to keep FTS5 in sync on INSERT and DELETE
"""

import sqlite3                  # stuff
import os                       # stuff
import sys                      # stuff
from typing import Optional     # stuff

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(_HERE, "aquarium.db")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_KB_RECORDS = """
CREATE TABLE IF NOT EXISTS kb_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    species_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    content      TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_KB_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    species_name,
    category,
    content,
    content='kb_records',
    content_rowid='id'
);
"""

_CREATE_TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS kb_ai AFTER INSERT ON kb_records BEGIN
    INSERT INTO kb_fts(rowid, species_name, category, content)
    VALUES (new.id, new.species_name, new.category, new.content);
END;
"""

_CREATE_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS kb_ad AFTER DELETE ON kb_records BEGIN
    INSERT INTO kb_fts(kb_fts, rowid, species_name, category, content)
    VALUES ('delete', old.id, old.species_name, old.category, old.content);
END;
"""

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class KBRecord:
    """Lightweight data class for a knowledge base record."""

    def __init__(self, id: int, species_name: str, category: str, content: str):
        self.id = id
        self.species_name = species_name
        self.category = category
        self.content = content

    def __repr__(self) -> str:
        return (
            f"KBRecord(id={self.id!r}, species_name={self.species_name!r}, "
            f"category={self.category!r}, content={self.content[:40]!r}...)"
        )

# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def create_schema(db_path: str) -> None:
    """
    Create the kb_records table, kb_fts FTS5 virtual table, and the
    INSERT / DELETE sync triggers if they do not already exist.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(_CREATE_KB_RECORDS)
        conn.execute(_CREATE_KB_FTS)
        conn.execute(_CREATE_TRIGGER_INSERT)
        conn.execute(_CREATE_TRIGGER_DELETE)
        conn.commit()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def insert_record(
    db_path: str,
    species_name: str,
    category: str,
    content: str,
) -> int:
    """
    Insert a new record into kb_records and return its auto-assigned id.

    The INSERT trigger automatically keeps kb_fts in sync.

    Malformed records (empty species_name, category, or content) are skipped:
    a warning is printed and -1 is returned so callers can detect the skip.

    Args:
        db_path:      Path to the SQLite database file.
        species_name: Fish/plant name or topic name (e.g. "Nitrogen Cycle").
        category:     One of "fish", "plant", "chemistry", "maintenance",
                        "disease", or "aquascaping".
        content:      Full care sheet or knowledge text.

    Returns:
        The integer primary key of the newly inserted row, or -1 if the
        record was skipped due to missing required fields.
    """
    if not species_name or not category or not content:
        print(
            f"[seed] WARNING: skipping malformed record -- "
            f"species_name={species_name!r}, category={category!r}, "
            f"content={'<empty>' if not content else '<present>'}",
            file=sys.stderr,
        )
        return -1

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO kb_records (species_name, category, content) VALUES (?, ?, ?)",
            (species_name, category, content),
        )
        conn.commit()
        return cursor.lastrowid


def get_record_by_id(db_path: str, record_id: int) -> Optional[KBRecord]:
    """
    Retrieve a single record from kb_records by its primary key.

    Args:
        db_path:   Path to the SQLite database file.
        record_id: The integer primary key to look up.

    Returns:
        A KBRecord instance if found, or None if no row with that id exists.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, species_name, category, content FROM kb_records WHERE id = ?",
            (record_id,),
        ).fetchone()

    if row is None:
        return None

    return KBRecord(
        id=row["id"],
        species_name=row["species_name"],
        category=row["category"],
        content=row["content"],
    )
# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED_RECORDS = [
    # -----------------------------------------------------------------------
    # FISH (24 species)
    # -----------------------------------------------------------------------
    (
        "Guppy", "fish",
        "Guppies (Poecilia reticulata) are one of the most popular freshwater fish for beginners. "
        "They thrive in water temperatures of 72-82 F and a pH of 6.8-7.8, and prefer a tank of at least 5 gallons. "
        "Males display vibrant, flowing tails and are peaceful community fish that do well with other small, non-aggressive species."
    ),
    (
        "Betta", "fish",
        "Betta fish (Betta splendens) are known for their brilliant colors and flowing fins. "
        "They require a minimum 5-gallon tank with a heater maintaining 76-82 F and a pH of 6.5-7.5. "
        "Males are highly territorial toward other bettas and should be kept alone or with peaceful, short-finned tank mates."
    ),
    (
        "Neon Tetra", "fish",
        "Neon Tetras (Paracheirodon innesi) are iconic schooling fish recognized by their vivid blue and red stripe. "
        "They prefer soft, slightly acidic water (pH 6.0-7.0) at 70-81 F and should be kept in groups of at least 6 in a 10-gallon or larger tank. "
        "They are peaceful and make excellent community fish with other small, non-aggressive species."
    ),
    (
        "Cardinal Tetra", "fish",
        "Cardinal Tetras (Paracheirodon axelrodi) closely resemble Neon Tetras but have a red stripe extending the full length of the body. "
        "They prefer soft, acidic water (pH 4.6-6.2) at 73-81 F and do best in groups of 6 or more in a well-planted tank. "
        "They are sensitive to water quality changes and require stable, well-cycled aquariums."
    ),
    (
        "Corydoras Catfish", "fish",
        "Corydoras catfish are small, armored bottom-dwellers that are excellent scavengers and peaceful community fish. "
        "They prefer temperatures of 72-79 F, a pH of 6.0-7.5, and a soft sandy substrate to protect their sensitive barbels. "
        "They are social fish and should be kept in groups of at least 4-6; a 20-gallon tank is recommended for a small group."
    ),
    (
        "Pleco (Common)", "fish",
        "Common Plecos (Hypostomus plecostomus) are algae-eating catfish that can grow up to 24 inches and require a large tank of 75 gallons or more as adults. "
        "They prefer temperatures of 72-86 F and a pH of 6.5-7.5, and need driftwood in the tank as part of their diet. "
        "Despite being sold as small juveniles, they grow quickly and are not suitable for small aquariums long-term."
    ),
    (
        "Molly", "fish",
        "Mollies (Poecilia sphenops) are hardy, adaptable livebearers that come in many color varieties including black, dalmatian, and balloon. "
        "They prefer slightly alkaline water (pH 7.5-8.5) at 72-82 F and can even tolerate brackish conditions. "
        "They are peaceful community fish that do well in groups; a 20-gallon tank is recommended for a small group."
    ),
    (
        "Platy", "fish",
        "Platies (Xiphophorus maculatus) are colorful, hardy livebearers that are ideal for beginners. "
        "They thrive in temperatures of 65-77 F and a pH of 7.0-8.0, making them tolerant of a wide range of water conditions. "
        "They are peaceful and do well in community tanks; a 10-gallon tank can house a small group comfortably."
    ),
    (
        "Swordtail", "fish",
        "Swordtails (Xiphophorus hellerii) are named for the elongated lower tail fin of the male. "
        "They prefer temperatures of 65-82 F and a pH of 7.0-8.3, and are active swimmers that need a tank of at least 20 gallons. "
        "They are generally peaceful but males can be aggressive toward each other, so keep one male per tank or a larger group."
    ),
    (
        "Angelfish", "fish",
        "Angelfish (Pterophyllum scalare) are elegant cichlids with distinctive triangular bodies and long, flowing fins. "
        "They require a tall tank of at least 30 gallons, temperatures of 76-84 F, and a pH of 6.0-7.5. "
        "They can be semi-aggressive, especially when breeding, and may eat very small fish like neon tetras."
    ),
    (
        "Discus", "fish",
        "Discus (Symphysodon spp.) are considered the king of the aquarium due to their stunning disc-shaped bodies and vibrant colors. "
        "They are demanding fish requiring very soft, acidic water (pH 6.0-7.0) at 82-88 F and a large tank of 55 gallons or more. "
        "They are best kept by experienced aquarists who can maintain pristine water quality and provide a varied, high-protein diet."
    ),
    (
        "Oscar", "fish",
        "Oscars (Astronotus ocellatus) are large, intelligent cichlids that can recognize their owners and even be hand-fed. "
        "They grow up to 12-14 inches and require a tank of at least 55 gallons (75+ for a pair), with temperatures of 74-81 F and pH 6.0-8.0. "
        "They are aggressive and will eat smaller fish; tank mates should be similarly sized and robust."
    ),
    (
        "Goldfish", "fish",
        "Goldfish (Carassius auratus) are cold-water fish that prefer temperatures of 65-72 F and a pH of 7.0-8.4. "
        "They are heavy waste producers and require excellent filtration; fancy varieties need at least 20 gallons per fish. "
        "Common and comet goldfish can grow over 12 inches and are best suited for ponds or very large aquariums."
    ),
    (
        "Zebra Danio", "fish",
        "Zebra Danios (Danio rerio) are fast, active schooling fish with distinctive horizontal blue and silver stripes. "
        "They are extremely hardy and tolerate a wide range of temperatures (64-77 F) and pH (6.5-7.5), making them ideal for beginners. "
        "They should be kept in groups of at least 5 in a 10-gallon or larger tank and are peaceful community fish."
    ),
    (
        "Cherry Barb", "fish",
        "Cherry Barbs (Puntius titteya) are peaceful, easy-to-keep barbs named for the bright red coloration of males. "
        "They prefer temperatures of 73-81 F and a pH of 6.0-7.5, and do best in a planted tank of at least 25 gallons. "
        "Unlike some barbs, they are not fin-nippers and make excellent community fish with other peaceful species."
    ),
    (
        "Tiger Barb", "fish",
        "Tiger Barbs (Puntigrus tetrazona) are energetic, striking fish with bold black vertical stripes on an orange body. "
        "They prefer temperatures of 68-79 F and a pH of 6.0-7.5, and should be kept in groups of 6 or more to reduce fin-nipping behavior. "
        "They are semi-aggressive and should not be kept with long-finned fish like bettas or angelfish."
    ),
    (
        "Harlequin Rasbora", "fish",
        "Harlequin Rasboras (Trigonostigma heteromorpha) are popular schooling fish with a distinctive black triangular patch on their body. "
        "They prefer soft, slightly acidic water (pH 6.0-7.5) at 72-81 F and should be kept in groups of 8 or more in a 10-gallon or larger tank. "
        "They are peaceful and do well in community tanks with other small, non-aggressive fish."
    ),
    (
        "Dwarf Gourami", "fish",
        "Dwarf Gouramis (Trichogaster lalius) are small, colorful labyrinth fish that breathe air from the surface. "
        "They prefer temperatures of 72-82 F and a pH of 6.0-7.5, and do well in a 10-gallon or larger planted tank. "
        "Males can be territorial toward each other but are generally peaceful with other species; they are sensitive to poor water quality."
    ),
    (
        "Pearl Gourami", "fish",
        "Pearl Gouramis (Trichopodus leerii) are elegant labyrinth fish covered in a pearl-like spotted pattern. "
        "They prefer temperatures of 77-82 F and a pH of 6.5-8.0, and require a tank of at least 30 gallons with plenty of plants and hiding spots. "
        "They are peaceful and hardy, making them a great choice for community tanks with other non-aggressive fish."
    ),
    (
        "Kuhli Loach", "fish",
        "Kuhli Loaches (Pangio kuhlii) are eel-like, nocturnal bottom-dwellers that are excellent scavengers. "
        "They prefer temperatures of 73-86 F and a pH of 5.5-6.5, and require a soft sandy substrate and plenty of hiding places. "
        "They are social and should be kept in groups of 3 or more; a 20-gallon tank is suitable for a small group."
    ),
    (
        "Otocinclus", "fish",
        "Otocinclus (Otocinclus spp.) are small, peaceful algae-eating catfish that are excellent for controlling algae in planted tanks. "
        "They prefer temperatures of 72-79 F and a pH of 6.0-7.5, and should be kept in groups of 4 or more in a well-established, cycled tank. "
        "They are sensitive to water quality and should not be added to new tanks; supplement their diet with algae wafers and blanched vegetables."
    ),
    (
        "Bristlenose Pleco", "fish",
        "Bristlenose Plecos (Ancistrus spp.) are a smaller alternative to the common pleco, reaching only 4-5 inches. "
        "They prefer temperatures of 60-80 F and a pH of 6.5-7.5, and require driftwood in the tank as part of their diet. "
        "They are excellent algae eaters and are suitable for tanks as small as 25 gallons, making them far more practical than common plecos."
    ),
    (
        "Rummy Nose Tetra", "fish",
        "Rummy Nose Tetras (Hemigrammus rhodostomus) are prized for their bright red nose and black-and-white striped tail. "
        "They prefer soft, acidic water (pH 5.5-7.0) at 75-84 F and should be kept in schools of 8 or more in a 20-gallon or larger tank. "
        "They are sensitive to water quality and are often used as indicator fish; a pale nose signals stress or poor water conditions."
    ),
    (
        "Black Skirt Tetra", "fish",
        "Black Skirt Tetras (Gymnocorymbus ternetzi) are hardy, active schooling fish with distinctive black fins and a silver-black body. "
        "They prefer temperatures of 70-85 F and a pH of 6.0-7.5, and should be kept in groups of 5 or more in a 15-gallon or larger tank. "
        "They can be mild fin-nippers and should not be kept with long-finned fish; they are otherwise peaceful community fish."
    ),

    # -----------------------------------------------------------------------
    # CHEMISTRY (5 parameters)
    # -----------------------------------------------------------------------
    (
        "Ammonia", "chemistry",
        "Ammonia (NH3/NH4+) is produced by fish waste, uneaten food, and decaying organic matter and is highly toxic to fish. "
        "Safe level: 0 ppm. Caution level: 0.25-0.5 ppm (stress and gill damage begin). Danger level: above 0.5 ppm (can be lethal within hours). "
        "Corrective actions include immediate partial water changes (25-50%), reducing feeding, and checking for dead fish or decaying matter. "
        "A fully cycled tank with healthy beneficial bacteria will convert ammonia to nitrite rapidly."
    ),
    (
        "Nitrite", "chemistry",
        "Nitrite (NO2-) is produced by beneficial bacteria (Nitrosomonas) converting ammonia and is toxic to fish even at low levels. "
        "Safe level: 0 ppm. Caution level: 0.25-0.5 ppm (interferes with oxygen transport in blood). Danger level: above 0.5 ppm (potentially lethal). "
        "Corrective actions include partial water changes, adding aquarium salt (1 tablespoon per 5 gallons) to reduce nitrite uptake, and checking filter health. "
        "Elevated nitrite indicates an incomplete nitrogen cycle or an overwhelmed biological filter."
    ),
    (
        "Nitrate", "chemistry",
        "Nitrate (NO3-) is the end product of the nitrogen cycle and is far less toxic than ammonia or nitrite but harmful at high levels. "
        "Safe level: 0-20 ppm. Caution level: 20-40 ppm (stress and reduced immunity). Danger level: above 40 ppm (chronic health issues and algae blooms). "
        "Corrective actions include regular partial water changes (25-30% weekly), reducing feeding, adding live plants, and not overstocking the tank. "
        "Nitrate is the primary reason regular water changes are essential in any aquarium."
    ),
    (
        "pH", "chemistry",
        "pH measures the acidity or alkalinity of aquarium water on a scale of 0-14, with 7.0 being neutral. "
        "Safe range for most community fish: 6.5-7.5. Caution range: 6.0-6.5 or 7.5-8.0 (species-dependent stress). Danger range: below 6.0 or above 8.5 (chemical burns and death). "
        "Corrective actions for low pH include adding crushed coral or baking soda; for high pH, use driftwood, peat moss, or pH-down products. "
        "Sudden pH swings are more dangerous than a stable pH outside the ideal range; always adjust pH gradually."
    ),
    (
        "Temperature", "chemistry",
        "Water temperature is critical for fish metabolism, immune function, and oxygen levels in the aquarium. "
        "Safe range for most tropical fish: 74-80 F (23-27 C). Caution range: 68-74 F or 80-84 F (metabolic stress). Danger range: below 60 F or above 90 F (thermal shock and death). "
        "Corrective actions for high temperature include floating ice packs, increasing surface agitation, and moving the tank away from heat sources. "
        "For low temperature, use a reliable aquarium heater with a thermostat and check it regularly with a separate thermometer."
    ),

    # -----------------------------------------------------------------------
    # MAINTENANCE (nitrogen cycle)
    # -----------------------------------------------------------------------
    (
        "Nitrogen Cycle", "maintenance",
        "The nitrogen cycle is the biological process that makes an aquarium safe for fish by converting toxic waste products into less harmful compounds. "
        "Stage 1 - Ammonia Spike: Fish waste and uneaten food produce ammonia (NH3). Ammonia levels rise sharply in a new tank (days 1-14). "
        "This stage is the most dangerous for fish; ammonia above 0.5 ppm causes gill damage and death. Beneficial bacteria (Nitrosomonas) begin colonizing the filter media. "
        "Stage 2 - Nitrite Spike: Nitrosomonas bacteria convert ammonia to nitrite (NO2-). Ammonia levels drop while nitrite spikes (days 7-21). "
        "Nitrite is also highly toxic and interferes with the blood ability to carry oxygen. A second group of bacteria (Nitrobacter/Nitrospira) begins colonizing. "
        "Stage 3 - Nitrate Accumulation: Nitrobacter/Nitrospira bacteria convert nitrite to nitrate (NO3-). Both ammonia and nitrite drop to 0 ppm while nitrate accumulates (days 14-42). "
        "The cycle is complete when ammonia and nitrite both read 0 ppm and nitrate is detectable. Regular partial water changes (25-30% weekly) keep nitrate below 20 ppm. "
        "To speed up cycling, add a bacterial starter culture, use filter media from an established tank, or use the fishless cycling method with pure ammonia."
    ),

    # -----------------------------------------------------------------------
    # DISEASE (5 conditions)
    # -----------------------------------------------------------------------
    (
        "Ich (White Spot Disease)", "disease",
        "Ich (Ichthyophthirius multifiliis) is the most common freshwater fish disease, caused by a parasitic protozoan. "
        "Symptoms include small white spots resembling grains of salt on the body and fins, flashing (rubbing against objects), lethargy, and loss of appetite. "
        "Treatment: Raise water temperature to 86 F (30 C) for 10 days to speed up the parasite life cycle, combined with an ich medication containing malachite green or formalin. "
        "Remove activated carbon from the filter during treatment. Quarantine new fish for 2-4 weeks before adding them to the main tank to prevent introduction."
    ),
    (
        "Fin Rot", "disease",
        "Fin Rot is a bacterial infection (commonly Aeromonas or Pseudomonas) that causes the fins to appear ragged, frayed, or discolored. "
        "It is usually caused by poor water quality, stress, or injury, and can progress to the body if untreated. "
        "Treatment: Improve water quality with a 25-30% water change, treat with an antibacterial medication such as API Fin and Body Cure or Melafix. "
        "In severe cases, a broad-spectrum antibiotic like erythromycin may be needed. Address the root cause (water quality, aggression) to prevent recurrence."
    ),
    (
        "Velvet Disease", "disease",
        "Velvet (Oodinium pilularis) is a parasitic disease that gives fish a gold or rust-colored dusty appearance, like velvet fabric. "
        "Symptoms include rapid gill movement, flashing, lethargy, and a fine gold or yellow dust on the body and fins. "
        "Treatment: Dim the tank lights (the parasite is photosynthetic), raise temperature to 82-86 F, and treat with a copper-based medication or formalin. "
        "Velvet is highly contagious and can kill fish quickly; treat the entire tank and quarantine new fish to prevent introduction."
    ),
    (
        "Dropsy", "disease",
        "Dropsy is a symptom rather than a single disease, characterized by severe bloating and raised scales that give the fish a pinecone appearance. "
        "It is caused by fluid accumulation in the body cavity, often due to bacterial infection (Aeromonas), kidney failure, or internal parasites. "
        "Treatment is difficult and often unsuccessful; isolate the affected fish immediately to prevent spreading. "
        "Treat with a broad-spectrum antibiotic like kanamycin or trimethoprim-sulfamethoxazole in a hospital tank. Improving water quality and reducing stress are essential preventive measures."
    ),
    (
        "Swim Bladder Disease", "disease",
        "Swim Bladder Disease affects a fish ability to control its buoyancy, causing it to float at the surface, sink to the bottom, or swim sideways. "
        "Common causes include overfeeding, constipation, bacterial infection, or physical injury. Fancy goldfish and bettas are particularly susceptible. "
        "Treatment: Fast the fish for 2-3 days, then feed a shelled, cooked pea to relieve constipation. "
        "If bacterial infection is suspected, treat with an antibiotic. Ensure the fish is not being bullied and that water quality is excellent."
    ),

    # -----------------------------------------------------------------------
    # PLANTS (7 species)
    # -----------------------------------------------------------------------
    (
        "Java Fern", "plant",
        "Java Fern (Microsorum pteropus) is one of the most popular and hardy aquarium plants, ideal for beginners. "
        "It grows slowly and thrives in low to medium light without CO2 injection, making it very low-maintenance. "
        "It should be attached to driftwood or rocks rather than planted in substrate, as burying the rhizome will cause it to rot. "
        "It tolerates a wide range of water parameters (pH 6.0-7.5, temperature 68-82 F) and is compatible with most fish."
    ),
    (
        "Anubias", "plant",
        "Anubias (Anubias spp.) are slow-growing, extremely hardy plants with thick, dark green leaves that are resistant to being eaten by fish. "
        "They thrive in low to medium light and do not require CO2 injection, making them perfect for low-tech setups. "
        "Like Java Fern, the rhizome must not be buried; attach it to driftwood or rocks with thread or glue. "
        "They prefer temperatures of 72-82 F and a pH of 6.0-7.5, and are compatible with virtually all freshwater fish."
    ),
    (
        "Java Moss", "plant",
        "Java Moss (Taxiphyllum barbieri) is a versatile, fast-growing moss that can be attached to any surface or left floating. "
        "It thrives in a wide range of conditions (pH 5.0-8.0, temperature 59-86 F) and requires no CO2 or special lighting. "
        "It provides excellent cover for fry and shrimp, and is commonly used to create moss walls, carpets, and decorative trees. "
        "It grows quickly and may need regular trimming to prevent it from overtaking the tank."
    ),
    (
        "Amazon Sword", "plant",
        "Amazon Sword (Echinodorus grisebachii) is a large, rosette-forming plant that makes an excellent centerpiece or background plant. "
        "It prefers moderate to high light and benefits from root tabs as it is a heavy root feeder. "
        "It grows best in temperatures of 72-82 F and a pH of 6.5-7.5, and can grow quite large (up to 20 inches), so it is best suited for tanks of 20 gallons or more. "
        "It is compatible with most fish but may be nibbled by herbivorous species like goldfish."
    ),
    (
        "Hornwort", "plant",
        "Hornwort (Ceratophyllum demersum) is a fast-growing, stem plant that is one of the easiest aquarium plants to keep. "
        "It can be planted in substrate or left floating, and thrives in a wide range of conditions (pH 6.0-7.5, temperature 59-86 F). "
        "Its rapid growth makes it an excellent nitrate absorber and algae competitor, helping to maintain water quality. "
        "It requires regular trimming and may shed needles when first introduced to a new tank."
    ),
    (
        "Water Sprite", "plant",
        "Water Sprite (Ceratopteris thalictroides) is a delicate, feathery plant that can be planted or left floating. "
        "It is a fast grower that thrives in moderate light and temperatures of 68-82 F with a pH of 6.0-7.5. "
        "When floating, it provides excellent shade and cover for surface-dwelling fish and fry. "
        "It is a heavy nutrient absorber and helps control algae; it propagates easily by producing plantlets on its leaves."
    ),
    (
        "Cryptocoryne", "plant",
        "Cryptocorynes (Cryptocoryne spp.) are popular, low-maintenance rosette plants that come in many sizes and colors. "
        "They prefer low to medium light and do not require CO2 injection, making them ideal for low-tech planted tanks. "
        "They are planted in substrate and are heavy root feeders that benefit from root tabs. "
        "They may experience crypt melt when first introduced (leaves dissolve), but will regrow from the roots; temperatures of 72-82 F and pH 6.0-7.5 are ideal."
    ),

    # -----------------------------------------------------------------------
    # AQUASCAPING (1 record)
    # -----------------------------------------------------------------------
    (
        "Aquascaping Basics", "aquascaping",
        "Aquascaping is the art of arranging aquatic plants, rocks, driftwood, and substrate to create an aesthetically pleasing underwater landscape. "
        "Substrate Types: Fine sand (1-2mm) is ideal for bottom-dwelling fish and most plants; aqua soil (e.g., ADA Amazonia) provides nutrients for planted tanks; gravel (2-5mm) is easy to clean but less plant-friendly. "
        "A substrate depth of 2-3 inches is recommended for most planted tanks, with deeper areas (3-4 inches) for root-feeding plants. "
        "Hardscape Placement: Use the rule of thirds to position focal points off-center for a natural look. Place larger rocks and driftwood first, then build around them. "
        "Odd numbers of rocks (3, 5, 7) create more natural-looking arrangements than even numbers. Lean rocks slightly inward to suggest geological strata. "
        "Plant Zones: Foreground plants (carpeting plants like dwarf hairgrass or Monte Carlo) should be short and low-growing. "
        "Midground plants (Anubias, Cryptocoryne, Java Fern) provide the main visual interest and should be medium height. "
        "Background plants (Amazon Sword, Vallisneria, Hornwort) should be tall and fill the back of the tank to hide equipment. "
        "Maintenance: Trim plants regularly to maintain the aquascape shape; remove dead leaves to prevent ammonia spikes. "
        "Perform regular water changes and dose fertilizers (macro and micro nutrients) to keep plants healthy and vibrant."
    ),
]


def seed_data(db_path: str) -> None:
    """
    Insert all required knowledge base records into the database.

    This function is idempotent with respect to schema -- it calls create_schema
    first to ensure the tables exist. However, it does NOT deduplicate records,
    so calling it multiple times will insert duplicate rows. To avoid duplicates,
    the function checks if records already exist and skips insertion if so.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    create_schema(db_path)

    # Check if data already exists to avoid duplicates on re-runs
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM kb_records").fetchone()[0]

    if count > 0:
        print(f"[seed] Database already contains {count} records. Skipping seed to avoid duplicates.")
        print("[seed] To re-seed, delete aquarium.db and run seed.py again.")
        return

    inserted = 0
    skipped = 0
    for species_name, category, content in _SEED_RECORDS:
        row_id = insert_record(db_path, species_name, category, content)
        if row_id == -1:
            skipped += 1
        else:
            inserted += 1

    print(f"[seed] Seeded {inserted} records ({skipped} skipped).")

    # Print a summary by category
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM kb_records GROUP BY category ORDER BY category"
        ).fetchall()
    print("[seed] Records by category:")
    for category, cnt in rows:
        print(f"  {category}: {cnt}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Create the database schema and seed all required knowledge base records
    at the default path (knowledge_base/aquarium.db).

    This function is safe to run multiple times -- the schema creation uses
    IF NOT EXISTS, and seed_data skips insertion if records already exist.
    """
    db_path = DEFAULT_DB_PATH
    print(f"[seed] Creating schema at: {db_path}")
    create_schema(db_path)
    print("[seed] Schema created successfully.")
    print("[seed] Tables: kb_records, kb_fts")
    print("[seed] Triggers: kb_ai (INSERT), kb_ad (DELETE)")
    print("[seed] Seeding knowledge base...")
    seed_data(db_path)
    print("[seed] Done.")


if __name__ == "__main__":
    main()
