CREATE TABLE properties (
    id                INTEGER PRIMARY KEY,
    address           TEXT,
    city_state_zip    TEXT,
    builder           TEXT,
    year_built        INTEGER,
    sqft              INTEGER,
    lot_sqft          INTEGER,
    bedrooms          INTEGER,
    bathrooms         REAL,
    property_type     TEXT,
    listed_price      REAL,
    price_per_sqft    REAL,
    condition_score   REAL,       -- 1-10, AI assessed
    estimated_value   REAL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE property_images (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    image_path        TEXT,
    ai_assessment     TEXT,       -- full JSON from Vision
    condition_score   INTEGER,
    issues_detected   TEXT,       -- JSON array
    confidence        TEXT,       -- high/medium/low
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE material_assessment (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    floor_type        TEXT,
    floor_condition   TEXT,
    floor_score       INTEGER,
    wood_species      TEXT,
    wood_grade        TEXT,
    paint_condition   TEXT,
    source            TEXT,       -- 'ai_photo' | 'inspection' | 'blueprint'
    confidence        TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE maintenance_needs (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    issue             TEXT,
    priority          TEXT,       -- urgent | moderate | low
    estimated_cost    REAL,
    value_uplift      REAL,
    roi_percent       REAL,
    category          TEXT,       -- maps to contractor category
    source            TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE inspection_forms (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    inspector_name_token TEXT,    -- tokenized PII
    inspection_date   TEXT,
    parsed_fields     TEXT,       -- full JSON of checkbox results
    total_reno_cost   REAL,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE documents (
    id                INTEGER PRIMARY KEY,
    property_id       INTEGER,
    doc_type          TEXT,       -- warranty | valuation_ref | inspection_report
    file_path         TEXT,
    pinecone_namespace TEXT,      -- null if not RAG'd
    key_findings      TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);

CREATE TABLE renovation_companies (
    id                INTEGER PRIMARY KEY,
    category          TEXT,
    company_name      TEXT,
    website           TEXT,
    location          TEXT,
    phone             TEXT
);

CREATE TABLE pii_token_map (
    id                INTEGER PRIMARY KEY,
    doc_id            TEXT,
    token             TEXT,
    original_value    TEXT,
    entity_type       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO renovation_companies (category, company_name, website, location, phone) VALUES
('Curb Appeal & Exterior Upgrades', 'Power HRG', 'https://www.powerhrg.com/', 'McKinney, TX', '214-306-7611'),
('Kitchen & Bathroom Updates', 'Spruced - Decorating Den', 'https://spruced.decoratingden.com/', 'Dallas, TX', '(214) 516-7677'),
('Flooring & Square Footage Upgrades', 'EFS Flooring and Remodeling', 'https://www.efsflooringandremodeling.com/', 'Irving, TX', '(972) 330-7615'),
('Essential System & Energy Updates', 'Kohler Home Energy', 'https://www.kohlerhomeenergy.rehlko.com/', 'Nationwide', '1-844-731-7989');
