-- fotky od lidí k budově nebo místu (soubor v R2, binding PHOTOS)
ALTER TABLE reports ADD COLUMN photo TEXT;     -- klíč souboru v R2 ("foto/…jpg"), jen u kind = 'foto'
ALTER TABLE reports ADD COLUMN author TEXT;    -- jméno pro uvedení autora (nepovinné)
ALTER TABLE reports ADD COLUMN license TEXT;   -- licence, se kterou autor souhlasil ('CC BY 4.0')
