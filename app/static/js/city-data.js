const turkiyeSehirleri = {
    Marmara: ["Istanbul", "Bursa", "Kocaeli", "Bilecik", "Balikesir", "Canakkale", "Edirne", "Kirklareli", "Tekirdag", "Yalova", "Sakarya", "Duzce"],
    Ege: ["Izmir", "Aydin", "Denizli", "Mugla", "Manisa", "Afyonkarahisar", "Kutahya", "Usak"],
    Akdeniz: ["Antalya", "Adana", "Mersin", "Hatay", "Osmaniye", "Kahramanmaras", "Gaziantep", "Kilis"],
    IcAnadolu: ["Ankara", "Konya", "Kayseri", "Eskisehir", "Sivas", "Yozgat", "Aksaray", "Nevsehir", "Kirikkale", "Karaman", "Kirsehir", "Nigde", "Cankiri"],
    Karadeniz: ["Trabzon", "Samsun", "Rize", "Ordu", "Giresun", "Sinop", "Amasya", "Tokat", "Artvin", "Gumushane", "Bayburt", "Kastamonu", "Bartin", "Karabuk", "Zonguldak", "Bolu", "Corum"],
    DoguAnadolu: ["Erzurum", "Van", "Malatya", "Elazig", "Bingol", "Tunceli", "Erzincan", "Ardahan", "Igdir", "Kars", "Agri", "Mus", "Bitlis", "Hakkari"],
    GuneydoguAnadolu: ["Diyarbakir", "Sanliurfa", "Mardin", "Batman", "Siirt", "Sirnak", "Adiyaman"]
};

const uluslararasiSehirler = [
    // North America & Caribbean
    { sehir: "Washington", code: "US", timezone: "America/New_York" }, { sehir: "New-York", code: "US", timezone: "America/New_York" }, { sehir: "Los-Angeles", code: "US", timezone: "America/Los_Angeles" },
    { sehir: "Ottawa", code: "CA", timezone: "America/Toronto" }, { sehir: "Toronto", code: "CA", timezone: "America/Toronto" }, { sehir: "Mexico-City", code: "MX", timezone: "America/Mexico_City" },
    { sehir: "Havana", code: "CU", timezone: "America/Havana" }, { sehir: "Guatemala-City", code: "GT", timezone: "America/Guatemala" }, { sehir: "San-Salvador", code: "SV", timezone: "America/El_Salvador" },
    { sehir: "Tegucigalpa", code: "HN", timezone: "America/Tegucigalpa" }, { sehir: "Managua", code: "NI", timezone: "America/Managua" }, { sehir: "San-Jose", code: "CR", timezone: "America/Costa_Rica" },
    { sehir: "Panama-City", code: "PA", timezone: "America/Panama" }, { sehir: "Kingston", code: "JM", timezone: "America/Jamaica" }, { sehir: "Santo-Domingo", code: "DO", timezone: "America/Santo_Domingo" },
    { sehir: "Port-au-Prince", code: "HT", timezone: "America/Port-au-Prince" }, { sehir: "Nassau", code: "BS", timezone: "America/Nassau" }, { sehir: "Belmopan", code: "BZ", timezone: "America/Belize" },
    { sehir: "Saint-Johns", code: "AG", timezone: "America/Antigua" }, { sehir: "Bridgetown", code: "BB", timezone: "America/Barbados" }, { sehir: "Roseau", code: "DM", timezone: "America/Dominica" },
    { sehir: "Saint-Georges", code: "GD", timezone: "America/Grenada" }, { sehir: "Basseterre", code: "KN", timezone: "America/St_Kitts" }, { sehir: "Castries", code: "LC", timezone: "America/St_Lucia" },
    { sehir: "Kingstown", code: "VC", timezone: "America/St_Vincent" }, { sehir: "Port-of-Spain", code: "TT", timezone: "America/Port_of_Spain" },
    { sehir: "Oranjestad", code: "AW", timezone: "America/Aruba" }, { sehir: "Willemstad", code: "CW", timezone: "America/Curacao" },

    // South America
    { sehir: "Brasilia", code: "BR", timezone: "America/Sao_Paulo" }, { sehir: "Sao-Paulo", code: "BR", timezone: "America/Sao_Paulo" }, { sehir: "Rio-de-Janeiro", code: "BR", timezone: "America/Sao_Paulo" },
    { sehir: "Buenos-Aires", code: "AR", timezone: "America/Argentina/Buenos_Aires" }, { sehir: "Santiago", code: "CL", timezone: "America/Santiago" }, { sehir: "Bogota", code: "CO", timezone: "America/Bogota" },
    { sehir: "Lima", code: "PE", timezone: "America/Lima" }, { sehir: "Caracas", code: "VE", timezone: "America/Caracas" }, { sehir: "Quito", code: "EC", timezone: "America/Guayaquil" },
    { sehir: "Asuncion", code: "PY", timezone: "America/Asuncion" }, { sehir: "Montevideo", code: "UY", timezone: "America/Montevideo" }, { sehir: "La-Paz", code: "BO", timezone: "America/La_Paz" },
    { sehir: "Georgetown", code: "GY", timezone: "America/Guyana" }, { sehir: "Paramaribo", code: "SR", timezone: "America/Paramaribo" }, { sehir: "Cayenne", code: "GF", timezone: "America/Cayenne" },

    // Europe (Western & Central)
    { sehir: "London", code: "GB", timezone: "Europe/London" }, { sehir: "Paris", code: "FR", timezone: "Europe/Paris" }, { sehir: "Berlin", code: "DE", timezone: "Europe/Berlin" },
    { sehir: "Rome", code: "IT", timezone: "Europe/Rome" }, { sehir: "Madrid", code: "ES", timezone: "Europe/Madrid" }, { sehir: "Amsterdam", code: "NL", timezone: "Europe/Amsterdam" },
    { sehir: "Brussels", code: "BE", timezone: "Europe/Brussels" }, { sehir: "Vienna", code: "AT", timezone: "Europe/Vienna" }, { sehir: "Bern", code: "CH", timezone: "Europe/Zurich" },
    { sehir: "Lisbon", code: "PT", timezone: "Europe/Lisbon" }, { sehir: "Athens", code: "GR", timezone: "Europe/Athens" }, { sehir: "Dublin", code: "IE", timezone: "Europe/Dublin" },
    { sehir: "Luxembourg", code: "LU", timezone: "Europe/Luxembourg" }, { sehir: "Monaco", code: "MC", timezone: "Europe/Monaco" }, { sehir: "Andorra-la-Vella", code: "AD", timezone: "Europe/Andorra" },
    { sehir: "Valletta", code: "MT", timezone: "Europe/Malta" }, { sehir: "San-Marino", code: "SM", timezone: "Europe/San_Marino" }, { sehir: "Vaduz", code: "LI", timezone: "Europe/Vaduz" },
    { sehir: "Vatican", code: "VA", timezone: "Europe/Vatican" },

    // Northern Europe
    { sehir: "Stockholm", code: "SE", timezone: "Europe/Stockholm" }, { sehir: "Oslo", code: "NO", timezone: "Europe/Oslo" }, { sehir: "Copenhagen", code: "DK", timezone: "Europe/Copenhagen" },
    { sehir: "Helsinki", code: "FI", timezone: "Europe/Helsinki" }, { sehir: "Reykjavik", code: "IS", timezone: "Atlantic/Reykjavik" },

    // Eastern Europe & Balkans
    { sehir: "Moscow", code: "RU", timezone: "Europe/Moscow" }, { sehir: "St.-Petersburg", code: "RU", timezone: "Europe/Moscow" }, { sehir: "Kazan", code: "RU", timezone: "Europe/Moscow" },
    { sehir: "Kiev", code: "UA", timezone: "Europe/Kiev" }, { sehir: "Warsaw", code: "PL", timezone: "Europe/Warsaw" }, { sehir: "Prague", code: "CZ", timezone: "Europe/Prague" },
    { sehir: "Budapest", code: "HU", timezone: "Europe/Budapest" }, { sehir: "Bucharest", code: "RO", timezone: "Europe/Bucharest" }, { sehir: "Sofia", code: "BG", timezone: "Europe/Sofia" },
    { sehir: "Belgrade", code: "RS", timezone: "Europe/Belgrade" }, { sehir: "Sarajevo", code: "BA", timezone: "Europe/Sarajevo" }, { sehir: "Skopje", code: "MK", timezone: "Europe/Skopje" },
    { sehir: "Tirana", code: "AL", timezone: "Europe/Tirane" }, { sehir: "Pristina", code: "XK", timezone: "Europe/Belgrade" }, { sehir: "Zagreb", code: "HR", timezone: "Europe/Zagreb" },
    { sehir: "Ljubljana", code: "SI", timezone: "Europe/Ljubljana" }, { sehir: "Bratislava", code: "SK", timezone: "Europe/Bratislava" }, { sehir: "Chisinau", code: "MD", timezone: "Europe/Chisinau" },
    { sehir: "Minsk", code: "BY", timezone: "Europe/Minsk" }, { sehir: "Tallinn", code: "EE", timezone: "Europe/Tallinn" }, { sehir: "Riga", code: "LV", timezone: "Europe/Riga" },
    { sehir: "Vilnius", code: "LT", timezone: "Europe/Vilnius" }, { sehir: "Podgorica", code: "ME", timezone: "Europe/Belgrade" },

    // Middle East & Caucasus
    { sehir: "Mecca", code: "SA", timezone: "Asia/Riyadh" }, { sehir: "Medina", code: "SA", timezone: "Asia/Riyadh" }, { sehir: "Riyadh", code: "SA", timezone: "Asia/Riyadh" },
    { sehir: "Baku", code: "AZ", timezone: "Asia/Baku" }, { sehir: "Nakhchivan", code: "AZ", timezone: "Asia/Baku" }, { sehir: "Tbilisi", code: "GE", timezone: "Asia/Tbilisi" },
    { sehir: "Yerevan", code: "AM", timezone: "Asia/Yerevan" }, { sehir: "Baghdad", code: "IQ", timezone: "Asia/Baghdad" }, { sehir: "Tehran", code: "IR", timezone: "Asia/Tehran" },
    { sehir: "Damascus", code: "SY", timezone: "Asia/Damascus" }, { sehir: "Beirut", code: "LB", timezone: "Asia/Beirut" }, { sehir: "Amman", code: "JO", timezone: "Asia/Amman" },
    { sehir: "Jerusalem", code: "IL", timezone: "Asia/Jerusalem" }, { sehir: "Palestine", code: "PS", timezone: "Asia/Gaza" }, { sehir: "Dubai", code: "AE", timezone: "Asia/Dubai" }, { sehir: "Kuwait", code: "KW", timezone: "Asia/Kuwait" },
    { sehir: "Doha", code: "QA", timezone: "Asia/Qatar" }, { sehir: "Muscat", code: "OM", timezone: "Asia/Muscat" }, { sehir: "Manama", code: "BH", timezone: "Asia/Bahrain" },
    { sehir: "Sanaa", code: "YE", timezone: "Asia/Aden" }, { sehir: "Nicosia", code: "CY", timezone: "Asia/Nicosia" },

    // Central & South Asia
    { sehir: "Nur-Sultan", code: "KZ", timezone: "Asia/Almaty" }, { sehir: "Almaty", code: "KZ", timezone: "Asia/Almaty" }, { sehir: "Tashkent", code: "UZ", timezone: "Asia/Tashkent" },
    { sehir: "Ashgabat", code: "TM", timezone: "Asia/Ashgabat" }, { sehir: "Bishkek", code: "KG", timezone: "Asia/Bishkek" }, { sehir: "Dushanbe", code: "TJ", timezone: "Asia/Dushanbe" },
    { sehir: "Kabul", code: "AF", timezone: "Asia/Kabul" }, { sehir: "Islamabad", code: "PK", timezone: "Asia/Karachi" }, { sehir: "New-Delhi", code: "IN", timezone: "Asia/Kolkata" },
    { sehir: "Dhaka", code: "BD", timezone: "Asia/Dhaka" }, { sehir: "Colombo", code: "LK", timezone: "Asia/Colombo" }, { sehir: "Kathmandu", code: "NP", timezone: "Asia/Kathmandu" },
    { sehir: "Thimphu", code: "BT", timezone: "Asia/Thimphu" }, { sehir: "Male", code: "MV", timezone: "Indian/Maldives" },

    // East Asia
    { sehir: "Tokyo", code: "JP", timezone: "Asia/Tokyo" }, { sehir: "Seoul", code: "KR", timezone: "Asia/Seoul" }, { sehir: "Beijing", code: "CN", timezone: "Asia/Shanghai" },
    { sehir: "Hong-Kong", code: "HK", timezone: "Asia/Hong_Kong" }, { sehir: "Ulaanbaatar", code: "MN", timezone: "Asia/Ulaanbaatar" }, { sehir: "Taipei", code: "TW", timezone: "Asia/Taipei" },
    { sehir: "Pyongyang", code: "KP", timezone: "Asia/Pyongyang" },
    
    // Southeast Asia
    { sehir: "Jakarta", code: "ID", timezone: "Asia/Jakarta" }, { sehir: "Singapore", code: "SG", timezone: "Asia/Singapore" }, { sehir: "Kuala-Lumpur", code: "MY", timezone: "Asia/Kuala_Lumpur" },
    { sehir: "Bangkok", code: "TH", timezone: "Asia/Bangkok" }, { sehir: "Manila", code: "PH", timezone: "Asia/Manila" }, { sehir: "Hanoi", code: "VN", timezone: "Asia/Ho_Chi_Minh" },
    { sehir: "Phnom-Penh", code: "KH", timezone: "Asia/Phnom_Penh" }, { sehir: "Vientiane", code: "LA", timezone: "Asia/Vientiane" }, { sehir: "Naypyidaw", code: "MM", timezone: "Asia/Yangon" },
    { sehir: "Bandar-Seri-Begawan", code: "BN", timezone: "Asia/Brunei" }, { sehir: "Dili", code: "TL", timezone: "Asia/Dili" },
    
    // Oceania
    { sehir: "Sydney", code: "AU", timezone: "Australia/Sydney" }, { sehir: "Melbourne", code: "AU", timezone: "Australia/Melbourne" }, { sehir: "Perth", code: "AU", timezone: "Australia/Perth" },
    { sehir: "Auckland", code: "NZ", timezone: "Pacific/Auckland" }, { sehir: "Port-Moresby", code: "PG", timezone: "Pacific/Port_Moresby" }, { sehir: "Suva", code: "FJ", timezone: "Pacific/Fiji" },
    { sehir: "Honiara", code: "SB", timezone: "Pacific/Guadalcanal" }, { sehir: "Port-Vila", code: "VU", timezone: "Pacific/Efate" }, { sehir: "Apia", code: "WS", timezone: "Pacific/Apia" },
    { sehir: "Nukualofa", code: "TO", timezone: "Pacific/Tongatapu" }, { sehir: "Palikir", code: "FM", timezone: "Pacific/Pohnpei" },
    { sehir: "Ngerulmud", code: "PW", timezone: "Pacific/Palau" },

    // North & West Africa
    { sehir: "Cairo", code: "EG", timezone: "Africa/Cairo" }, { sehir: "Tripoli", code: "LY", timezone: "Africa/Tripoli" }, { sehir: "Tunis", code: "TN", timezone: "Africa/Tunis" },
    { sehir: "Algiers", code: "DZ", timezone: "Africa/Algiers" }, { sehir: "Rabat", code: "MA", timezone: "Africa/Casablanca" }, { sehir: "Casablanca", code: "MA", timezone: "Africa/Casablanca" }, { sehir: "Khartoum", code: "SD", timezone: "Africa/Khartoum" },
    { sehir: "Abuja", code: "NG", timezone: "Africa/Lagos" }, { sehir: "Lagos", code: "NG", timezone: "Africa/Lagos" }, { sehir: "Dakar", code: "SN", timezone: "Africa/Dakar" }, { sehir: "Accra", code: "GH", timezone: "Africa/Accra" },
    { sehir: "Bamako", code: "ML", timezone: "Africa/Bamako" }, { sehir: "Niamey", code: "NE", timezone: "Africa/Niamey" }, { sehir: "Ouagadougou", code: "BF", timezone: "Africa/Ouagadougou" },
    { sehir: "Conakry", code: "GN", timezone: "Africa/Conakry" }, { sehir: "Freetown", code: "SL", timezone: "Africa/Freetown" }, { sehir: "Monrovia", code: "LR", timezone: "Africa/Monrovia" },
    { sehir: "Abidjan", code: "CI", timezone: "Africa/Abidjan" }, { sehir: "Lome", code: "TG", timezone: "Africa/Lome" }, { sehir: "Porto-Novo", code: "BJ", timezone: "Africa/Porto-Novo" },
    { sehir: "Banjul", code: "GM", timezone: "Africa/Banjul" }, { sehir: "Bissau", code: "GW", timezone: "Africa/Bissau" }, { sehir: "Praia", code: "CV", timezone: "Atlantic/Cape_Verde" },
    { sehir: "Nouakchott", code: "MR", timezone: "Africa/Nouakchott" },

    // Central & East Africa
    { sehir: "Kinshasa", code: "CD", timezone: "Africa/Kinshasa" }, { sehir: "Brazzaville", code: "CG", timezone: "Africa/Brazzaville" }, { sehir: "Libreville", code: "GA", timezone: "Africa/Libreville" },
    { sehir: "Yaounde", code: "CM", timezone: "Africa/Douala" }, { sehir: "N-Djamena", code: "TD", timezone: "Africa/Ndjamena" }, { sehir: "Bangui", code: "CF", timezone: "Africa/Bangui" },
    { sehir: "Malabo", code: "GQ", timezone: "Africa/Malabo" }, { sehir: "Sao-Tome", code: "ST", timezone: "Africa/Sao_Tome" }, { sehir: "Nairobi", code: "KE", timezone: "Africa/Nairobi" },
    { sehir: "Addis-Ababa", code: "ET", timezone: "Africa/Addis_Ababa" }, { sehir: "Mogadishu", code: "SO", timezone: "Africa/Mogadishu" }, { sehir: "Djibouti", code: "DJ", timezone: "Africa/Djibouti" },
    { sehir: "Asmara", code: "ER", timezone: "Africa/Asmara" }, { sehir: "Kampala", code: "UG", timezone: "Africa/Kampala" }, { sehir: "Dodoma", code: "TZ", timezone: "Africa/Dar_es_Salaam" },
    { sehir: "Kigali", code: "RW", timezone: "Africa/Kigali" }, { sehir: "Bujumbura", code: "BI", timezone: "Africa/Bujumbura" }, { sehir: "Juba", code: "SS", timezone: "Africa/Juba" },
    
    // Southern Africa & Islands
    { sehir: "Pretoria", code: "ZA", timezone: "Africa/Johannesburg" }, { sehir: "Cape-Town", code: "ZA", timezone: "Africa/Johannesburg" }, { sehir: "Windhoek", code: "NA", timezone: "Africa/Windhoek" },
    { sehir: "Gaborone", code: "BW", timezone: "Africa/Gaborone" }, { sehir: "Harare", code: "ZW", timezone: "Africa/Harare" }, { sehir: "Lusaka", code: "ZM", timezone: "Africa/Lusaka" },
    { sehir: "Maputo", code: "MZ", timezone: "Africa/Maputo" }, { sehir: "Lilongwe", code: "MW", timezone: "Africa/Blantyre" }, { sehir: "Mbabane", code: "SZ", timezone: "Africa/Mbabane" },
    { sehir: "Maseru", code: "LS", timezone: "Africa/Maseru" }, { sehir: "Luanda", code: "AO", timezone: "Africa/Luanda" }, { sehir: "Antananarivo", code: "MG", timezone: "Indian/Antananarivo" },
    { sehir: "Port-Louis", code: "MU", timezone: "Indian/Mauritius" }, { sehir: "Victoria", code: "SC", timezone: "Indian/Mahe" }, { sehir: "Moroni", code: "KM", timezone: "Indian/Comoro" },
    { sehir: "Saint-Denis", code: "RE", timezone: "Indian/Reunion" }
];
const buyukSehirler = ["Istanbul", "Ankara", "Izmir", "Adana", "Bursa", "Gaziantep", "Konya", "Kayseri", "Antalya", "Diyarbakir", "Eskisehir", "Erzurum", "Mersin", "Kocaeli", "Samsun", "Sakarya", "Aydin", "Balikesir", "Denizli", "Hatay", "Malatya", "Manisa", "Kahramanmaras", "Mardin", "Mugla", "Ordu", "Tekirdag", "Trabzon", "Sanliurfa", "Van"];