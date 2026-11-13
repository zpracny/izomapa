-- stav mapy z administrace (vánoční výzdoba, zamrzlé rybníky); worker tabulku založí i sám
CREATE TABLE IF NOT EXISTS nastaveni (k TEXT PRIMARY KEY, v TEXT NOT NULL);
