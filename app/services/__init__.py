import os
import json
import time
import requests
from datetime import datetime, timedelta
import pytz
from app.extensions import db, cache
from app.models import EzanVakti, DailyContent, Guide
from flask import request, session
from .ramadan_service import RamadanService

# Varsayılan değerler
DEFAULT_COUNTRY = 'TR'
DEFAULT_CITY = 'Istanbul'
DEFAULT_TZ = 'Europe/Istanbul'

# Ülke kodları ve Türkçe adları eşlemesi
COUNTRY_NAME_MAPPING = {
    # Türkiye
    'TR': 'Türkiye',
    # Kuzey Amerika
    'US': 'Amerika Birleşik Devletleri',
    'CA': 'Kanada',
    'MX': 'Meksika',
    # Orta Amerika
    'CU': 'Küba',
    'GT': 'Guatemala',
    'SV': 'El Salvador',
    'HN': 'Honduras',
    'NI': 'Nikaragua',
    'CR': 'Kosta Rika',
    'PA': 'Panama',
    # Karayipler
    'JM': 'Jamaika',
    'DO': 'Dominik Cumhuriyeti',
    'HT': 'Haiti',
    'BS': 'Bahamalar',
    'BZ': 'Belize',
    'AG': 'Antigua ve Barbuda',
    'BB': 'Barbados',
    'DM': 'Dominika',
    'GD': 'Grenada',
    'KN': 'Saint Kitts ve Nevis',
    'LC': 'Saint Lucia',
    'VC': 'Saint Vincent ve Grenadinler',
    'TT': 'Trinidad ve Tobago',
    'AW': 'Aruba',
    'CW': 'Curaçao',
    # Güney Amerika
    'BR': 'Brezilya',
    'AR': 'Arjantin',
    'CL': 'Şili',
    'CO': 'Kolombiya',
    'PE': 'Peru',
    'VE': 'Venezuela',
    'EC': 'Ekvador',
    'PY': 'Paraguay',
    'UY': 'Uruguay',
    'BO': 'Bolivya',
    'GY': 'Guyana',
    'SR': 'Surinam',
    'GF': 'Fransız Guyanası',
    # Batı Avrupa
    'GB': 'Birleşik Krallık',
    'FR': 'Fransa',
    'DE': 'Almanya',
    'IT': 'İtalya',
    'ES': 'İspanya',
    'NL': 'Hollanda',
    'BE': 'Belçika',
    'AT': 'Avusturya',
    'CH': 'İsviçre',
    'PT': 'Portekiz',
    'GR': 'Yunanistan',
    'IE': 'İrlanda',
    'LU': 'Lüksemburg',
    'MC': 'Monako',
    'AD': 'Andorra',
    'MT': 'Malta',
    'SM': 'San Marino',
    'LI': 'Lihtenştayn',
    'VA': 'Vatikan',
    # Kuzey Avrupa
    'SE': 'İsveç',
    'NO': 'Norveç',
    'DK': 'Danimarka',
    'FI': 'Finlandiya',
    'IS': 'İzlanda',
    # Doğu Avrupa
    'RU': 'Rusya',
    'UA': 'Ukrayna',
    'PL': 'Polonya',
    'CZ': 'Çek Cumhuriyeti',
    'HU': 'Macaristan',
    'RO': 'Romanya',
    'BG': 'Bulgaristan',
    'RS': 'Sırbistan',
    'BA': 'Bosna Hersek',
    'MK': 'Kuzey Makedonya',
    'AL': 'Arnavutluk',
    'XK': 'Kosova',
    'HR': 'Hırvatistan',
    'SI': 'Slovenya',
    'SK': 'Slovakya',
    'MD': 'Moldova',
    'BY': 'Belarus',
    'EE': 'Estonya',
    'LV': 'Letonya',
    'LT': 'Litvanya',
    'ME': 'Karadağ',
    # Orta Doğu
    'SA': 'Suudi Arabistan',
    'AZ': 'Azerbaycan',
    'GE': 'Gürcistan',
    'AM': 'Ermenistan',
    'IQ': 'Irak',
    'IR': 'İran',
    'SY': 'Suriye',
    'LB': 'Lübnan',
    'JO': 'Ürdün',
    'IL': 'İsrail',
    'PS': 'Filistin',
    'AE': 'Birleşik Arap Emirlikleri',
    'KW': 'Kuveyt',
    'QA': 'Katar',
    'OM': 'Umman',
    'BH': 'Bahreyn',
    'YE': 'Yemen',
    'CY': 'Kıbrıs',
    # Asya
    'KZ': 'Kazakistan',
    'UZ': 'Özbekistan',
    'TM': 'Türkmenistan',
    'KG': 'Kırgızistan',
    'TJ': 'Tacikistan',
    'AF': 'Afganistan',
    'PK': 'Pakistan',
    'IN': 'Hindistan',
    'BD': 'Bangladeş',
    'LK': 'Sri Lanka',
    'NP': 'Nepal',
    'BT': 'Butan',
    'MV': 'Maldivler',
    'JP': 'Japonya',
    'KR': 'Güney Kore',
    'CN': 'Çin',
    'HK': 'Hong Kong',
    'MO': 'Makao',
    'MN': 'Moğolistan',
    'TW': 'Tayvan',
    'KP': 'Kuzey Kore',
    'ID': 'Endonezya',
    'SG': 'Singapur',
    'MY': 'Malezya',
    'TH': 'Tayland',
    'PH': 'Filipinler',
    'VN': 'Vietnam',
    'KH': 'Kamboçya',
    'LA': 'Lao',
    'MM': 'Myanmar',
    'BN': 'Brunei',
    'TL': 'Doğu Timor',
    # Okyanusya
    'AU': 'Avustralya',
    'NZ': 'Yeni Zelanda',
    'PG': 'Papua Yeni Gine',
    'FJ': 'Fiji',
    'SB': 'Solomon Adaları',
    'VU': 'Vanuatu',
    'WS': 'Samoa',
    'TO': 'Tonga',
    'FM': 'Mikronezya',
    'PW': 'Palau',
    # Kuzey Afrika
    'EG': 'Mısır',
    'LY': 'Libya',
    'TN': 'Tunus',
    'DZ': 'Cezayir',
    'MA': 'Fas',
    'SD': 'Sudan',
    # Batı Afrika
    'NG': 'Nijerya',
    'SN': 'Senegal',
    'GH': 'Gana',
    'ML': 'Mali',
    'NE': 'Nijer',
    'BF': 'Burkina Faso',
    'GN': 'Gine',
    'SL': 'Sierra Leone',
    'LR': 'Liberya',
    'CI': 'Fildişi Sahili',
    'TG': 'Togo',
    'BJ': 'Benin',
    'GM': 'Gambiya',
    'GW': 'Gine-Bissau',
    'CV': 'Cape Verde',
    'MR': 'Moritanya',
    # Orta Afrika
    'CD': 'Kongo Demokratik Cumhuriyeti',
    'CG': 'Kongo Cumhuriyeti',
    'GA': 'Gabon',
    'CM': 'Kamerun',
    'TD': 'Çad',
    'CF': 'Orta Afrika Cumhuriyeti',
    'GQ': 'Ekvator Ginesi',
    'ST': 'São Tomé ve Príncipe',
    # Doğu Afrika
    'KE': 'Kenya',
    'ET': 'Etiyopya',
    'SO': 'Somali',
    'DJ': 'Cibuti',
    'ER': 'Eritre',
    'UG': 'Uganda',
    'TZ': 'Tanzanya',
    'RW': 'Ruanda',
    'BI': 'Burundi',
    'SS': 'Güney Sudan',
    # Güney Afrika
    'ZA': 'Güney Afrika',
    'NA': 'Namibya',
    'BW': 'Botswana',
    'ZW': 'Zimbabve',
    'ZM': 'Zambiya',
    'MZ': 'Mozambik',
    'MW': 'Malavi',
    'SZ': 'Esvatini',
    'LS': 'Lesoto',
    'AO': 'Angola',
    'MG': 'Madagaskar',
    'MU': 'Mauritius',
    'SC': 'Seyşeller',
    'KM': 'Komorlar',
    'RE': 'Reunion'
}

# Şehir isimlerini Türkçe karakterli göstermek için eşleme
CITY_DISPLAY_NAME_MAPPING = {
    # Türkiye
    "Adiyaman": "Adıyaman", "Agri": "Ağrı", "Aydin": "Aydın", "Balikesir": "Balıkesir", "Bingol": "Bingöl",
    "Bitlis": "Bitlis", "Cankiri": "Çankırı", "Corum": "Çorum", "Diyarbakir": "Diyarbakır", "Duzce": "Düzce",
    "Elazig": "Elazığ", "Gumushane": "Gümüşhane", "Igdir": "Iğdır", "Istanbul": "İstanbul", "Izmir": "İzmir",
    "Kahramanmaras": "Kahramanmaraş", "Karabuk": "Karabük", "Kirikkale": "Kırıkkale", "Kirklareli": "Kırklareli",
    "Kirsehir": "Kırşehir", "Kutahya": "Kütahya", "Mus": "Muş", "Nigde": "Niğde", "Sanliurfa": "Şanlıurfa",
    "Sirnak": "Şırnak", "Tekirdag": "Tekirdağ", "Usak": "Uşak",
    # Uluslararası
    "Washington": "Washington", "New-York": "New York", "Los-Angeles": "Los Angeles",
    "Ottawa": "Ottawa", "Toronto": "Toronto", "Mexico-City": "Mexico City",
    "Havana": "Havana", "Guatemala-City": "Guatemala City", "San-Salvador": "San Salvador",
    "Tegucigalpa": "Tegucigalpa", "Managua": "Managua", "San-Jose": "San José",
    "Panama-City": "Panama City", "Kingston": "Kingston", "Santo-Domingo": "Santo Domingo",
    "Port-au-Prince": "Port-au-Prince", "Nassau": "Nassau", "Belmopan": "Belmopan",
    "Saint-Johns": "Saint John's", "Bridgetown": "Bridgetown", "Roseau": "Roseau",
    "Saint-Georges": "Saint George's", "Basseterre": "Basseterre", "Castries": "Castries",
    "Kingstown": "Kingstown", "Port-of-Spain": "Port of Spain", "Oranjestad": "Oranjestad",
    "Willemstad": "Willemstad", "Brasilia": "Brasília", "Sao-Paulo": "São Paulo",
    "Rio-de-Janeiro": "Rio de Janeiro", "Buenos-Aires": "Buenos Aires",
    "Santiago": "Santiago", "Bogota": "Bogotá", "Lima": "Lima",
    "Caracas": "Caracas", "Quito": "Quito", "Asuncion": "Asunción",
    "Montevideo": "Montevideo", "La-Paz": "La Paz", "Georgetown": "Georgetown",
    "Paramaribo": "Paramaribo", "Cayenne": "Cayenne", "London": "London",
    "Paris": "Paris", "Berlin": "Berlin", "Rome": "Rome", "Madrid": "Madrid",
    "Amsterdam": "Amsterdam", "Brussels": "Brussels", "Vienna": "Vienna",
    "Bern": "Bern", "Lisbon": "Lisbon", "Athens": "Athens", "Dublin": "Dublin",
    "Luxembourg": "Luxembourg", "Monaco": "Monaco", "Andorra-la-Vella": "Andorra la Vella",
    "Valletta": "Valletta", "San-Marino": "San Marino", "Vaduz": "Vaduz",
    "Vatican": "Vatican City", "Stockholm": "Stockholm", "Oslo": "Oslo",
    "Copenhagen": "Copenhagen", "Helsinki": "Helsinki", "Reykjavik": "Reykjavik",
    "Moscow": "Moscow", "St.-Petersburg": "St. Petersburg", "Kazan": "Kazan",
    "Kiev": "Kyiv", "Warsaw": "Warsaw", "Prague": "Prague",
    "Budapest": "Budapest", "Bucharest": "Bucharest", "Sofia": "Sofia",
    "Belgrade": "Belgrade", "Sarajevo": "Sarajevo", "Skopje": "Skopje",
    "Tirana": "Tirana", "Pristina": "Pristina", "Zagreb": "Zagreb",
    "Ljubljana": "Ljubljana", "Bratislava": "Bratislava", "Chisinau": "Chisinau",
    "Minsk": "Minsk", "Tallinn": "Tallinn", "Riga": "Riga",
    "Vilnius": "Vilnius", "Podgorica": "Podgorica", "Mecca": "Mekke",
    "Medina": "Medine", "Riyadh": "Riyadh", "Baku": "Baku",
    "Nakhchivan": "Nakhchivan", "Tbilisi": "Tbilisi", "Yerevan": "Yerevan",
    "Baghdad": "Baghdad", "Tehran": "Tehran", "Damascus": "Damascus",
    "Beirut": "Beirut", "Amman": "Amman", "Jerusalem": "Kudüs",
    "Dubai": "Dubai", "Kuwait": "Kuwait", "Doha": "Doha",
    "Muscat": "Muscat", "Manama": "Manama", "Sanaa": "Sana'a",
    "Nicosia": "Nicosia", "Nur-Sultan": "Nur-Sultan", "Almaty": "Almaty",
    "Tashkent": "Tashkent", "Ashgabat": "Ashgabat", "Bishkek": "Bishkek",
    "Dushanbe": "Dushanbe", "Kabul": "Kabul", "Islamabad": "Islamabad",
    "New-Delhi": "New Delhi", "Dhaka": "Dhaka", "Colombo": "Colombo",
    "Kathmandu": "Kathmandu", "Thimphu": "Thimphu", "Male": "Malé",
    "Tokyo": "Tokyo", "Seoul": "Seoul", "Beijing": "Beijing",
    "Hong-Kong": "Hong Kong", "Ulaanbaatar": "Ulaanbaatar", "Taipei": "Taipei",
    "Pyongyang": "Pyongyang", "Jakarta": "Jakarta", "Singapore": "Singapore",
    "Kuala-Lumpur": "Kuala Lumpur", "Bangkok": "Bangkok",
    "Manila": "Manila", "Hanoi": "Hanoi", "Phnom-Penh": "Phnom Penh",
    "Vientiane": "Vientiane", "Naypyidaw": "Naypyidaw",
    "Bandar-Seri-Begawan": "Bandar Seri Begawan", "Dili": "Dili",
    "Sydney": "Sydney", "Melbourne": "Melbourne", "Perth": "Perth",
    "Auckland": "Auckland", "Port-Moresby": "Port Moresby", "Suva": "Suva",
    "Honiara": "Honiara", "Port-Vila": "Port Vila", "Apia": "Apia",
    "Nukualofa": "Nukuʻalofa", "Palikir": "Palikir", "Ngerulmud": "Ngerulmud",
    "Cairo": "Cairo", "Tripoli": "Tripoli", "Tunis": "Tunis",
    "Algiers": "Algiers", "Rabat": "Rabat", "Casablanca": "Casablanca",
    "Khartoum": "Khartoum", "Abuja": "Abuja", "Lagos": "Lagos",
    "Dakar": "Dakar", "Accra": "Accra", "Bamako": "Bamako",
    "Niamey": "Niamey", "Ouagadougou": "Ouagadougou", "Conakry": "Conakry",
    "Freetown": "Freetown", "Monrovia": "Monrovia", "Abidjan": "Abidjan",
    "Lome": "Lomé", "Porto-Novo": "Porto-Novo", "Banjul": "Banjul",
    "Bissau": "Bissau", "Praia": "Praia", "Nouakchott": "Nouakchott",
    "Kinshasa": "Kinshasa", "Brazzaville": "Brazzaville",
    "Libreville": "Libreville", "Yaounde": "Yaoundé", "N-Djamena": "N'Djamena",
    "Bangui": "Bangui", "Malabo": "Malabo", "Sao-Tome": "São Tomé",
    "Nairobi": "Nairobi", "Addis-Ababa": "Addis Ababa", "Mogadishu": "Mogadishu",
    "Djibouti": "Djibouti", "Asmara": "Asmara", "Kampala": "Kampala",
    "Dodoma": "Dodoma", "Kigali": "Kigali", "Bujumbura": "Bujumbura",
    "Juba": "Juba", "Pretoria": "Pretoria", "Cape-Town": "Cape Town",
    "Windhoek": "Windhoek", "Gaborone": "Gaborone", "Harare": "Harare",
    "Lusaka": "Lusaka", "Maputo": "Maputo", "Lilongwe": "Lilongwe",
    "Mbabane": "Mbabane", "Maseru": "Maseru", "Luanda": "Luanda",
    "Antananarivo": "Antananarivo", "Port-Louis": "Port Louis",
    "Victoria": "Victoria", "Moroni": "Moroni", "Saint-Denis": "Saint-Denis"
}

# Uygulama kök dizinini al
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Bellek içi singleton veriler
_CITY_TIMEZONE_MAPPING_CACHE = None

def get_timezone_for_city(sehir, country_code='TR'):
    """
    Şehir ve ülke koduna göre timezone döndürür.
    """
    global _CITY_TIMEZONE_MAPPING_CACHE
    if _CITY_TIMEZONE_MAPPING_CACHE is None:
        _CITY_TIMEZONE_MAPPING_CACHE = {
            # Turkey
            ('istanbul', 'tr'): 'Europe/Istanbul',
            ('ankara', 'tr'): 'Europe/Istanbul',
            ('izmir', 'tr'): 'Europe/Istanbul',
            # International - North America & Caribbean
            ('washington', 'us'): 'America/New_York',
            ('new-york', 'us'): 'America/New_York',
            ('los-angeles', 'us'): 'America/Los_Angeles',
            ('ottawa', 'ca'): 'America/Toronto',
            ('toronto', 'ca'): 'America/Toronto',
            ('mexico-city', 'mx'): 'America/Mexico_City',
            ('havana', 'cu'): 'America/Havana',
            ('guatemala-city', 'gt'): 'America/Guatemala',
            ('san-salvador', 'sv'): 'America/El_Salvador',
            ('tegucigalpa', 'hn'): 'America/Tegucigalpa',
            ('managua', 'ni'): 'America/Managua',
            ('san-jose', 'cr'): 'America/Costa_Rica',
            ('panama-city', 'pa'): 'America/Panama',
            ('kingston', 'jm'): 'America/Jamaica',
            ('santo-domingo', 'do'): 'America/Santo_Domingo',
            ('port-au-prince', 'ht'): 'America/Port-au-Prince',
            ('nassau', 'bs'): 'America/Nassau',
            ('belmopan', 'bz'): 'America/Belize',
            ('saint-johns', 'ag'): 'America/Antigua',
            ('bridgetown', 'bb'): 'America/Barbados',
            ('roseau', 'dm'): 'America/Dominica',
            ('saint-georges', 'gd'): 'America/Grenada',
            ('basseterre', 'kn'): 'America/St_Kitts',
            ('castries', 'lc'): 'America/St_Lucia',
            ('kingstown', 'vc'): 'America/St_Vincent',
            ('port-of-spain', 'tt'): 'America/Port_of_Spain',
            ('oranjestad', 'aw'): 'America/Aruba',
            ('willemstad', 'cw'): 'America/Curacao',
            # South America
            ('brasilia', 'br'): 'America/Sao_Paulo',
            ('sao-paulo', 'br'): 'America/Sao_Paulo',
            ('rio-de-janeiro', 'br'): 'America/Sao_Paulo',
            ('buenos-aires', 'ar'): 'America/Argentina/Buenos_Aires',
            ('santiago', 'cl'): 'America/Santiago',
            ('bogota', 'co'): 'America/Bogota',
            ('lima', 'pe'): 'America/Lima',
            ('caracas', 've'): 'America/Caracas',
            ('quito', 'ec'): 'America/Guayaquil',
            ('asuncion', 'py'): 'America/Asuncion',
            ('montevideo', 'uy'): 'America/Montevideo',
            ('la-paz', 'bo'): 'America/La_Paz',
            ('georgetown', 'gy'): 'America/Guyana',
            ('paramaribo', 'sr'): 'America/Paramaribo',
            ('cayenne', 'gf'): 'America/Cayenne',
            # Europe (Western & Central)
            ('london', 'gb'): 'Europe/London',
            ('paris', 'fr'): 'Europe/Paris',
            ('berlin', 'de'): 'Europe/Berlin',
            ('rome', 'it'): 'Europe/Rome',
            ('madrid', 'es'): 'Europe/Madrid',
            ('amsterdam', 'nl'): 'Europe/Amsterdam',
            ('brussels', 'be'): 'Europe/Brussels',
            ('vienna', 'at'): 'Europe/Vienna',
            ('bern', 'ch'): 'Europe/Zurich',
            ('lisbon', 'pt'): 'Europe/Lisbon',
            ('athens', 'gr'): 'Europe/Athens',
            ('dublin', 'ie'): 'Europe/Dublin',
            ('luxembourg', 'lu'): 'Europe/Luxembourg',
            ('monaco', 'mc'): 'Europe/Monaco',
            ('andorra-la-vella', 'ad'): 'Europe/Andorra',
            ('valletta', 'mt'): 'Europe/Malta',
            ('san-marino', 'sm'): 'Europe/San_Marino',
            ('vaduz', 'li'): 'Europe/Vaduz',
            ('vatican', 'va'): 'Europe/Vatican',
            # Northern Europe
            ('stockholm', 'se'): 'Europe/Stockholm',
            ('oslo', 'no'): 'Europe/Oslo',
            ('copenhagen', 'dk'): 'Europe/Copenhagen',
            ('helsinki', 'fi'): 'Europe/Helsinki',
            ('reykjavik', 'is'): 'Atlantic/Reykjavik',
            # Eastern Europe & Balkans
            ('moscow', 'ru'): 'Europe/Moscow',
            ('st.-petersburg', 'ru'): 'Europe/Moscow',
            ('kazan', 'ru'): 'Europe/Moscow',
            ('kiev', 'ua'): 'Europe/Kiev',
            ('warsaw', 'pl'): 'Europe/Warsaw',
            ('prague', 'cz'): 'Europe/Prague',
            ('budapest', 'hu'): 'Europe/Budapest',
            ('bucharest', 'ro'): 'Europe/Bucharest',
            ('sofia', 'bg'): 'Europe/Sofia',
            ('belgrade', 'rs'): 'Europe/Belgrade',
            ('sarajevo', 'ba'): 'Europe/Sarajevo',
            ('skopje', 'mk'): 'Europe/Skopje',
            ('tirana', 'al'): 'Europe/Tirane',
            ('pristina', 'xk'): 'Europe/Belgrade',
            ('zagreb', 'hr'): 'Europe/Zagreb',
            ('ljubljana', 'si'): 'Europe/Ljubljana',
            ('bratislava', 'sk'): 'Europe/Bratislava',
            ('chisinau', 'md'): 'Europe/Chisinau',
            ('minsk', 'by'): 'Europe/Minsk',
            ('tallinn', 'ee'): 'Europe/Tallinn',
            ('riga', 'lv'): 'Europe/Riga',
            ('vilnius', 'lt'): 'Europe/Vilnius',
            ('podgorica', 'me'): 'Europe/Belgrade',
            # Middle East & Caucasus
            ('mecca', 'sa'): 'Asia/Riyadh',
            ('medina', 'sa'): 'Asia/Riyadh',
            ('riyadh', 'sa'): 'Asia/Riyadh',
            ('baku', 'az'): 'Asia/Baku',
            ('nakhchivan', 'az'): 'Asia/Baku',
            ('tbilisi', 'ge'): 'Asia/Tbilisi',
            ('yerevan', 'am'): 'Asia/Yerevan',
            ('baghdad', 'iq'): 'Asia/Baghdad',
            ('tehran', 'ir'): 'Asia/Tehran',
            ('damascus', 'sy'): 'Asia/Damascus',
            ('beirut', 'lb'): 'Asia/Beirut',
            ('amman', 'jo'): 'Asia/Amman',
            ('jerusalem', 'il'): 'Asia/Jerusalem',
            ('dubai', 'ae'): 'Asia/Dubai',
            ('kuwait', 'kw'): 'Asia/Kuwait',
            ('doha', 'qa'): 'Asia/Qatar',
            ('muscat', 'om'): 'Asia/Muscat',
            ('manama', 'bh'): 'Asia/Bahrain',
            ('sanaa', 'ye'): 'Asia/Aden',
            ('nicosia', 'cy'): 'Asia/Nicosia',
            # Central & South Asia
            ('nur-sultan', 'kz'): 'Asia/Almaty',
            ('almaty', 'kz'): 'Asia/Almaty',
            ('tashkent', 'uz'): 'Asia/Tashkent',
            ('ashgabat', 'tm'): 'Asia/Ashgabat',
            ('bishkek', 'kg'): 'Asia/Bishkek',
            ('dushanbe', 'tj'): 'Asia/Dushanbe',
            ('kabul', 'af'): 'Asia/Kabul',
            ('islamabad', 'pk'): 'Asia/Karachi',
            ('new-delhi', 'in'): 'Asia/Kolkata',
            ('dhaka', 'bd'): 'Asia/Dhaka',
            ('colombo', 'lk'): 'Asia/Colombo',
            ('kathmandu', 'np'): 'Asia/Kathmandu',
            ('thimphu', 'bt'): 'Asia/Thimphu',
            ('male', 'mv'): 'Indian/Maldives',
            # East Asia
            ('tokyo', 'jp'): 'Asia/Tokyo',
            ('seoul', 'kr'): 'Asia/Seoul',
            ('beijing', 'cn'): 'Asia/Shanghai',
            ('hong-kong', 'hk'): 'Asia/Hong_Kong',
            ('ulaanbaatar', 'mn'): 'Asia/Ulaanbaatar',
            ('taipei', 'tw'): 'Asia/Taipei',
            ('pyongyang', 'kp'): 'Asia/Pyongyang',
            # Southeast Asia
            ('jakarta', 'id'): 'Asia/Jakarta',
            ('singapore', 'sg'): 'Asia/Singapore',
            ('kuala-lumpur', 'my'): 'Asia/Kuala_Lumpur',
            ('bangkok', 'th'): 'Asia/Bangkok',
            ('manila', 'ph'): 'Asia/Manila',
            ('hanoi', 'vn'): 'Asia/Ho_Chi_Minh',
            ('phnom-penh', 'kh'): 'Asia/Phnom_Penh',
            ('vientiane', 'la'): 'Asia/Vientiane',
            ('naypyidaw', 'mm'): 'Asia/Yangon',
            ('bandar-seri-begawan', 'bn'): 'Asia/Brunei',
            ('dili', 'tl'): 'Asia/Dili',
            # Oceania
            ('sydney', 'au'): 'Australia/Sydney',
            ('melbourne', 'au'): 'Australia/Melbourne',
            ('perth', 'au'): 'Australia/Perth',
            ('auckland', 'nz'): 'Pacific/Auckland',
            ('port-moresby', 'pg'): 'Pacific/Port_Moresby',
            ('suva', 'fj'): 'Pacific/Fiji',
            ('honiara', 'sb'): 'Pacific/Guadalcanal',
            ('port-vila', 'vu'): 'Pacific/Efate',
            ('apia', 'ws'): 'Pacific/Apia',
            ('nukualofa', 'to'): 'Pacific/Tongatapu',
            ('palikir', 'fm'): 'Pacific/Pohnpei',
            ('ngerulmud', 'pw'): 'Pacific/Palau',
            # North & West Africa
            ('cairo', 'eg'): 'Africa/Cairo',
            ('tripoli', 'ly'): 'Africa/Tripoli',
            ('tunis', 'tn'): 'Africa/Tunis',
            ('algiers', 'dz'): 'Africa/Algiers',
            ('rabat', 'ma'): 'Africa/Casablanca',
            ('casablanca', 'ma'): 'Africa/Casablanca',
            ('khartoum', 'sd'): 'Africa/Khartoum',
            ('abuja', 'ng'): 'Africa/Lagos',
            ('lagos', 'ng'): 'Africa/Lagos',
            ('dakar', 'sn'): 'Africa/Dakar',
            ('accra', 'gh'): 'Africa/Accra',
            ('bamako', 'ml'): 'Africa/Bamako',
            ('niamey', 'ne'): 'Africa/Niamey',
            ('ouagadougou', 'bf'): 'Africa/Ouagadougou',
            ('conakry', 'gn'): 'Africa/Conakry',
            ('freetown', 'sl'): 'Africa/Freetown',
            ('monrovia', 'lr'): 'Africa/Monrovia',
            ('abidjan', 'ci'): 'Africa/Abidjan',
            ('lome', 'tg'): 'Africa/Lome',
            ('porto-novo', 'bj'): 'Africa/Porto-Novo',
            ('banjul', 'gm'): 'Africa/Banjul',
            ('bissau', 'gw'): 'Africa/Bissau',
            ('praia', 'cv'): 'Atlantic/Cape_Verde',
            ('nouakchott', 'mr'): 'Africa/Nouakchott',
            # Central & East Africa
            ('kinshasa', 'cd'): 'Africa/Kinshasa',
            ('brazzaville', 'cg'): 'Africa/Brazzaville',
            ('libreville', 'ga'): 'Africa/Libreville',
            ('yaounde', 'cm'): 'Africa/Douala',
            ('n-djamena', 'td'): 'Africa/Ndjamena',
            ('bangui', 'cf'): 'Africa/Bangui',
            ('malabo', 'gq'): 'Africa/Malabo',
            ('sao-tome', 'st'): 'Africa/Sao_Tome',
            ('nairobi', 'ke'): 'Africa/Nairobi',
            ('addis-ababa', 'et'): 'Africa/Addis_Ababa',
            ('mogadishu', 'so'): 'Africa/Mogadishu',
            ('djibouti', 'dj'): 'Africa/Djibouti',
            ('asmara', 'er'): 'Africa/Asmara',
            ('kampala', 'ug'): 'Africa/Kampala',
            ('dodoma', 'tz'): 'Africa/Dar_es_Salaam',
            ('kigali', 'rw'): 'Africa/Kigali',
            ('bujumbura', 'bi'): 'Africa/Bujumbura',
            ('juba', 'ss'): 'Africa/Juba',
            # Southern Africa & Islands
            ('pretoria', 'za'): 'Africa/Johannesburg',
            ('cape-town', 'za'): 'Africa/Johannesburg',
            ('windhoek', 'na'): 'Africa/Windhoek',
            ('gaborone', 'bw'): 'Africa/Gaborone',
            ('harare', 'zw'): 'Africa/Harare',
            ('lusaka', 'zm'): 'Africa/Lusaka',
            ('maputo', 'mz'): 'Africa/Maputo',
            ('lilongwe', 'mw'): 'Africa/Blantyre',
            ('mbabane', 'sz'): 'Africa/Mbabane',
            ('maseru', 'ls'): 'Africa/Maseru',
            ('luanda', 'ao'): 'Africa/Luanda',
            ('antananarivo', 'mg'): 'Indian/Antananarivo',
            ('port-louis', 'mu'): 'Indian/Mauritius',
            ('victoria', 'sc'): 'Indian/Mahe',
            ('moroni', 'km'): 'Indian/Comoro',
            ('saint-denis', 're'): 'Indian/Reunion'
        }
    
    # Doğrudan erişim (O(1))
    return _CITY_TIMEZONE_MAPPING_CACHE.get((sehir.lower(), country_code.lower()), DEFAULT_TZ)

def get_country_for_city(sehir):
    """Şehrin bağlı olduğu ülke kodunu döndürür."""
    mapping = {
        # Türkiye
        'Istanbul': 'TR', 'Ankara': 'TR', 'Izmir': 'TR',
        # North America & Caribbean
        'Washington': 'US', 'New-York': 'US', 'Los-Angeles': 'US',
        'Ottawa': 'CA', 'Toronto': 'CA', 'Mexico-City': 'MX', 'Havana': 'CU',
        'Guatemala-City': 'GT', 'San-Salvador': 'SV', 'Tegucigalpa': 'HN',
        'Managua': 'NI', 'San-Jose': 'CR', 'Panama-City': 'PA',
        'Kingston': 'JM', 'Santo-Domingo': 'DO', 'Port-au-Prince': 'HT',
        'Nassau': 'BS', 'Belmopan': 'BZ', 'Saint-Johns': 'AG',
        'Bridgetown': 'BB', 'Roseau': 'DM', 'Saint-Georges': 'GD',
        'Basseterre': 'KN', 'Castries': 'LC', 'Kingstown': 'VC',
        'Port-of-Spain': 'TT', 'Oranjestad': 'AW', 'Willemstad': 'CW',
        # South America
        'Brasilia': 'BR', 'Sao-Paulo': 'BR', 'Rio-de-Janeiro': 'BR',
        'Buenos-Aires': 'AR', 'Santiago': 'CL', 'Bogota': 'CO',
        'Lima': 'PE', 'Caracas': 'VE', 'Quito': 'EC',
        'Asuncion': 'PY', 'Montevideo': 'UY', 'La-Paz': 'BO',
        'Georgetown': 'GY', 'Paramaribo': 'SR', 'Cayenne': 'GF',
        # Europe (Western & Central)
        'London': 'GB', 'Paris': 'FR', 'Berlin': 'DE', 'Rome': 'IT',
        'Madrid': 'ES', 'Amsterdam': 'NL', 'Brussels': 'BE', 'Vienna': 'AT',
        'Bern': 'CH', 'Lisbon': 'PT', 'Athens': 'GR', 'Dublin': 'IE',
        'Luxembourg': 'LU', 'Monaco': 'MC', 'Andorra-la-Vella': 'AD',
        'Valletta': 'MT', 'San-Marino': 'SM', 'Vaduz': 'LI', 'Vatican': 'VA',
        # Northern Europe
        'Stockholm': 'SE', 'Oslo': 'NO', 'Copenhagen': 'DK', 'Helsinki': 'FI',
        'Reykjavik': 'IS',
        # Eastern Europe & Balkans
        'Moscow': 'RU', 'St.-Petersburg': 'RU', 'Kazan': 'RU',
        'Kiev': 'UA', 'Warsaw': 'PL', 'Prague': 'CZ', 'Budapest': 'HU',
        'Bucharest': 'RO', 'Sofia': 'BG', 'Belgrade': 'RS', 'Sarajevo': 'BA',
        'Skopje': 'MK', 'Tirana': 'AL', 'Pristina': 'XK', 'Zagreb': 'HR',
        'Ljubljana': 'SI', 'Bratislava': 'SK', 'Chisinau': 'MD', 'Minsk': 'BY',
        'Tallinn': 'EE', 'Riga': 'LV', 'Vilnius': 'LT', 'Podgorica': 'ME',
        # Middle East & Caucasus
        'Mecca': 'SA', 'Medina': 'SA', 'Riyadh': 'SA', 'Baku': 'AZ',
        'Nakhchivan': 'AZ', 'Tbilisi': 'GE', 'Yerevan': 'AM', 'Baghdad': 'IQ',
        'Tehran': 'IR', 'Damascus': 'SY', 'Beirut': 'LB', 'Amman': 'JO',
        'Jerusalem': 'IL', 'Dubai': 'AE', 'Kuwait': 'KW', 'Doha': 'QA',
        'Muscat': 'OM', 'Manama': 'BH', 'Sanaa': 'YE', 'Nicosia': 'CY',
        # Central & South Asia
        'Nur-Sultan': 'KZ', 'Almaty': 'KZ', 'Tashkent': 'UZ', 'Ashgabat': 'TM',
        'Bishkek': 'KG', 'Dushanbe': 'TJ', 'Kabul': 'AF', 'Islamabad': 'PK',
        'New-Delhi': 'IN', 'Dhaka': 'BD', 'Colombo': 'LK', 'Kathmandu': 'NP',
        'Thimphu': 'BT', 'Male': 'MV',
        # East Asia
        'Tokyo': 'JP', 'Seoul': 'KR', 'Beijing': 'CN', 'Hong-Kong': 'HK',
        'Ulaanbaatar': 'MN', 'Taipei': 'TW', 'Pyongyang': 'KP',
        # Southeast Asia
        'Jakarta': 'ID', 'Singapore': 'SG', 'Kuala-Lumpur': 'MY', 'Bangkok': 'TH',
        'Manila': 'PH', 'Hanoi': 'VN', 'Phnom-Penh': 'KH', 'Vientiane': 'LA',
        'Naypyidaw': 'MM', 'Bandar-Seri-Begawan': 'BN', 'Dili': 'TL',
        # Oceania
        'Sydney': 'AU', 'Melbourne': 'AU', 'Perth': 'AU', 'Auckland': 'NZ',
        'Port-Moresby': 'PG', 'Suva': 'FJ', 'Honiara': 'SB', 'Port-Vila': 'VU',
        'Apia': 'WS', 'Nukualofa': 'TO', 'Palikir': 'FM', 'Ngerulmud': 'PW',
        # North & West Africa
        'Cairo': 'EG', 'Tripoli': 'LY', 'Tunis': 'TN', 'Algiers': 'DZ',
        'Rabat': 'MA', 'Casablanca': 'MA', 'Khartoum': 'SD', 'Abuja': 'NG',
        'Lagos': 'NG', 'Dakar': 'SN', 'Accra': 'GH', 'Bamako': 'ML',
        'Niamey': 'NE', 'Ouagadougou': 'BF', 'Conakry': 'GN', 'Freetown': 'SL',
        'Monrovia': 'LR', 'Abidjan': 'CI', 'Lome': 'TG', 'Porto-Novo': 'BJ',
        'Banjul': 'GM', 'Bissau': 'GW', 'Praia': 'CV', 'Nouakchott': 'MR',
        # Central & East Africa
        'Kinshasa': 'CD', 'Brazzaville': 'CG', 'Libreville': 'GA', 'Yaounde': 'CM',
        'N-Djamena': 'TD', 'Bangui': 'CF', 'Malabo': 'GQ', 'Sao-Tome': 'ST',
        'Nairobi': 'KE', 'Addis-Ababa': 'ET', 'Mogadishu': 'SO', 'Djibouti': 'DJ',
        'Asmara': 'ER', 'Kampala': 'UG', 'Dodoma': 'TZ', 'Kigali': 'RW',
        'Bujumbura': 'BI', 'Juba': 'SS',
        # Southern Africa & Islands
        'Pretoria': 'ZA', 'Cape-Town': 'ZA', 'Windhoek': 'NA', 'Gaborone': 'BW',
        'Harare': 'ZW', 'Lusaka': 'ZM', 'Maputo': 'MZ', 'Lilongwe': 'MW',
        'Mbabane': 'SZ', 'Maseru': 'LS', 'Luanda': 'AO', 'Antananarivo': 'MG',
        'Port-Louis': 'MU', 'Victoria': 'SC', 'Moroni': 'KM', 'Saint-Denis': 'RE'
    }
    return mapping.get(sehir, 'TR')

def get_current_date(timezone_str=DEFAULT_TZ):
    """Verilen timezone'a göre yerel saati döndürür."""
    tz = pytz.timezone(timezone_str)
    return datetime.now(tz)

class UserService:
    @staticmethod
    def get_current_user_preferences(db_session=None):
        """Kullanıcının tercih ettiği şehir ve ülkeyi döndürür. (Session > Default)"""
        # Session Kontrolü
        try:
            if 'sehir' in session:
                return {
                    'sehir': session.get('sehir'),
                    'country_code': session.get('country_code', DEFAULT_COUNTRY)
                }
        except RuntimeError:
            pass
        
        # Varsayılan
        return {'sehir': DEFAULT_CITY, 'country_code': DEFAULT_COUNTRY}

    @staticmethod
    def save_user_preferences(sehir, country_code=DEFAULT_COUNTRY, db_session=None):
        try:
            session['sehir'] = sehir
            session['country_code'] = country_code
        except RuntimeError:
            pass

    @staticmethod
    def get_sehirler(country_code=DEFAULT_COUNTRY):
        # Ülkeye göre şehir listesi
        if country_code == 'TR':
            return [
                "Adana", "Adiyaman", "Afyonkarahisar", "Agri", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
                "Aydin", "Balikesir", "Bartin", "Batman", "Bayburt", "Bilecik", "Bingol", "Bitlis", "Bolu", "Burdur", "Bursa",
                "Canakkale", "Cankiri", "Corum", "Denizli", "Diyarbakir", "Duzce", "Edirne", "Elazig", "Erzincan", "Erzurum",
                "Eskisehir", "Gaziantep", "Giresun", "Gumushane", "Hakkari", "Hatay", "Igdir", "Isparta", "Istanbul", "Izmir",
                "Kahramanmaras", "Karabuk", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kirikkale", "Kirklareli", "Kirsehir",
                "Kilis", "Kocaeli", "Konya", "Kutahya", "Malatya", "Manisa", "Mardin", "Mersin", "Mugla", "Mus", "Nevsehir",
                "Nigde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Sanliurfa", "Siirt", "Sinop", "Sirnak", "Sivas",
                "Tekirdag", "Tokat", "Trabzon", "Tunceli", "Usak", "Van", "Yalova", "Yozgat", "Zonguldak"
            ]
        elif country_code == 'INT':
            return [
                "Washington", "New-York", "Los-Angeles", "Ottawa", "Toronto", "Mexico-City", "Havana",
                "Guatemala-City", "San-Salvador", "Tegucigalpa", "Managua", "San-Jose", "Panama-City",
                "Kingston", "Santo-Domingo", "Port-au-Prince", "Nassau", "Belmopan", "Saint-Johns",
                "Bridgetown", "Roseau", "Saint-Georges", "Basseterre", "Castries", "Kingstown",
                "Port-of-Spain", "Oranjestad", "Willemstad",
                "Brasilia", "Sao-Paulo", "Rio-de-Janeiro", "Buenos-Aires", "Santiago", "Bogota", "Lima", "Caracas",
                "Quito", "Asuncion", "Montevideo", "La-Paz", "Georgetown", "Paramaribo", "Cayenne",
                "London", "Paris", "Berlin", "Rome", "Madrid", "Amsterdam", "Brussels", "Vienna", "Bern", "Lisbon",
                "Athens", "Dublin", "Luxembourg", "Monaco", "Andorra-la-Vella", "Valletta", "San-Marino", "Vaduz", "Vatican",
                "Stockholm", "Oslo", "Copenhagen", "Helsinki", "Reykjavik",
                "Moscow", "St.-Petersburg", "Kazan", "Kiev", "Warsaw", "Prague", "Budapest", "Bucharest", "Sofia",
                "Belgrade", "Sarajevo", "Skopje", "Tirana", "Pristina", "Zagreb",
                "Ljubljana", "Bratislava", "Chisinau", "Minsk", "Tallinn", "Riga", "Vilnius", "Podgorica",
                "Mecca", "Medina", "Riyadh", "Baku", "Nakhchivan", "Tbilisi", "Yerevan", "Baghdad", "Tehran",
                "Damascus", "Beirut", "Amman", "Jerusalem", "Dubai", "Kuwait", "Doha", "Muscat", "Manama",
                "Sanaa", "Nicosia",
                "Nur-Sultan", "Almaty", "Tashkent", "Ashgabat", "Bishkek", "Dushanbe", "Kabul", "Islamabad",
                "New-Delhi", "Dhaka", "Colombo", "Kathmandu", "Thimphu", "Male",
                "Tokyo", "Seoul", "Beijing", "Hong-Kong", "Ulaanbaatar", "Taipei", "Pyongyang",
                "Jakarta", "Singapore", "Kuala-Lumpur", "Bangkok", "Manila", "Hanoi", "Phnom-Penh", "Vientiane",
                "Naypyidaw", "Bandar-Seri-Begawan", "Dili",
                "Sydney", "Melbourne", "Perth", "Auckland", "Port-Moresby", "Suva", "Honiara", "Port-Vila",
                "Apia", "Nukualofa", "Palikir", "Ngerulmud",
                "Cairo", "Tripoli", "Tunis", "Algiers", "Rabat", "Casablanca", "Khartoum", "Abuja", "Lagos",
                "Dakar", "Accra", "Bamako", "Niamey", "Ouagadougou", "Conakry", "Freetown",
                "Monrovia", "Abidjan", "Lome", "Porto-Novo", "Banjul", "Bissau", "Praia", "Nouakchott",
                "Kinshasa", "Brazzaville", "Libreville", "Yaounde", "N-Djamena", "Bangui",
                "Malabo", "Sao-Tome", "Nairobi", "Addis-Ababa", "Mogadishu", "Djibouti",
                "Asmara", "Kampala", "Dodoma", "Kigali", "Bujumbura", "Juba",
                "Pretoria", "Cape-Town", "Windhoek", "Gaborone", "Harare", "Lusaka",
                "Maputo", "Lilongwe", "Mbabane", "Maseru", "Luanda", "Antananarivo",
                "Port-Louis", "Victoria", "Moroni", "Saint-Denis"
            ]
        elif country_code == 'ALL':
            return UserService.get_sehirler('TR') + UserService.get_sehirler('INT')
        return [DEFAULT_CITY]

class PrayerService:
    _CACHE_TTL = 3600  # Varsayılan 1 saat

    @staticmethod
    def _calculate_dynamic_ttl(tz_str):
        """
        Gece yarısına kadar olan süreyi saniye cinsinden hesaplar.
        En az 3600 saniye (1 saat) döner.
        """
        try:
            tz = pytz.timezone(tz_str)
            now = datetime.now(tz)
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            ttl = int((tomorrow - now).total_seconds())
            return max(ttl, 3600)
        except Exception:
            return 3600

    @staticmethod
    def get_vakitler(sehir, country_code=None, tarih_dt=None, db_session=None):
        """
        Merkezi vakit alma servisi. Timezone-aware çalışır.
        Sıralama: Cache -> DB -> API
        """
        if db_session is None:
            db_session = db.session

        # Eğer country_code verilmemişse veya 'TR' ise ama şehir uluslararası listedeyse düzelt
        if country_code is None or country_code == 'TR':
            detected_country = get_country_for_city(sehir)
            country_code = detected_country
        
        timezone_str = get_timezone_for_city(sehir, country_code)
        tz = pytz.timezone(timezone_str)

        # Eğer tarih verilmemişse o timezone'un "bugün"ünü al
        if tarih_dt is None:
            tarih_dt = datetime.now(tz)
        elif isinstance(tarih_dt, str):
            tarih_dt = datetime.strptime(tarih_dt, "%Y-%m-%d")
        
        # Tarihi timezone-aware yap
        if tarih_dt.tzinfo is None:
            tarih_dt = tz.localize(tarih_dt)
            
        tarih_str = tarih_dt.strftime("%Y-%m-%d")
        
        # 1. Flask-Caching Kontrolü
        cache_key = f"vakitler_{country_code}_{sehir}_{tarih_str}_{timezone_str}"
        cached_data = cache.get(cache_key)
        if cached_data:
            from flask import current_app
            current_app.logger.debug(f"Cache Hit: {cache_key}")
            return cached_data
        
        from flask import current_app
        current_app.logger.debug(f"Cache Miss: {cache_key}")
        
        # 2. DB Kontrolü
        try:
            vakit = db_session.query(EzanVakti).filter_by(
                sehir=sehir, country_code=country_code, tarih=tarih_dt.date()
            ).first()
            if vakit:
                res = {
                    "imsak": vakit.imsak, "gunes": vakit.gunes, "ogle": vakit.ogle,
                    "ikindi": vakit.ikindi, "aksam": vakit.aksam, "yatsi": vakit.yatsi,
                    "timezone": vakit.timezone
                }
                # Cache'e ekle
                cache.set(cache_key, res, timeout=PrayerService._CACHE_TTL)
                return res
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"DB query error for {sehir}: {e}")
        
        # 3. API Fallback
        if country_code == 'TR':
            diyanet_vakit = PrayerService._get_from_diyanet(sehir, tarih_dt)
            if diyanet_vakit:
                PrayerService._save_to_db(sehir, country_code, timezone_str, tarih_dt.date(), diyanet_vakit, db_session)
                res = {**diyanet_vakit, "timezone": timezone_str}
                # Dinamik TTL hesapla (Gece yarısına kadar)
                dynamic_ttl = PrayerService._calculate_dynamic_ttl(timezone_str)
                cache.set(cache_key, res, timeout=dynamic_ttl)
                return res
        else:
            # Uluslararası şehirler için Aladhan API
            aladhan_vakit = PrayerService._get_from_aladhan(sehir, country_code, tarih_dt)
            if aladhan_vakit:
                PrayerService._save_to_db(sehir, country_code, timezone_str, tarih_dt.date(), aladhan_vakit, db_session)
                res = {**aladhan_vakit, "timezone": timezone_str}
                # Dinamik TTL hesapla (Gece yarısına kadar)
                dynamic_ttl = PrayerService._calculate_dynamic_ttl(timezone_str)
                cache.set(cache_key, res, timeout=dynamic_ttl)
                return res

        # Son çare: Boş veri döndür
        return {
            "imsak": "--:--", "gunes": "--:--", "ogle": "--:--",
            "ikindi": "--:--", "aksam": "--:--", "yatsi": "--:--",
            "timezone": timezone_str
        }

    @staticmethod
    def get_next_vakit(sehir, country_code=DEFAULT_COUNTRY, simdi=None):
        """
        Bir sonraki ezan vaktini ve kalan süreyi hesaplar.
        Gece yarısı ve timezone farklarını gözetir.
        """
        timezone_str = get_timezone_for_city(sehir, country_code)
        tz = pytz.timezone(timezone_str)

        if simdi is None:
            simdi = datetime.now(tz)
        elif simdi.tzinfo is None:
            simdi = tz.localize(simdi)
            
        bugun = simdi.date()
        vakitler = PrayerService.get_vakitler(sehir, country_code, simdi)
        
        yarin = simdi + timedelta(days=1)
        yarin_vakitler = PrayerService.get_vakitler(sehir, country_code, yarin)
        
        vakit_sirasi = ["imsak", "gunes", "ogle", "ikindi", "aksam", "yatsi"]
        
        # Bugünün kalan vakitlerini kontrol et
        for vakit_adi in vakit_sirasi:
            vakit_saati_str = vakitler.get(vakit_adi)
            if not vakit_saati_str or vakit_saati_str in ["null", "--:--"]:
                continue
                
            try:
                # Vakit saatini o günün tarihiyle birleştir ve timezone-aware yap
                vakit_zamani = tz.localize(datetime.strptime(f"{bugun.strftime('%Y-%m-%d')} {vakit_saati_str}", "%Y-%m-%d %H:%M"))
                
                if vakit_zamani > simdi:
                    return {
                        "sonraki_vakit": vakit_adi,
                        "vakit": vakit_saati_str,
                        "kalan_sure": int((vakit_zamani - simdi).total_seconds()),
                        "timezone": timezone_str
                    }
            except ValueError:
                continue
        
        # Eğer bugün bittiyse yarının ilk vaktini (imsak) döndür
        yarin_imsak_str = yarin_vakitler.get("imsak")
        if yarin_imsak_str and yarin_imsak_str not in ["null", "--:--"]:
            try:
                vakit_zamani = tz.localize(datetime.strptime(f"{yarin.strftime('%Y-%m-%d')} {yarin_imsak_str}", "%Y-%m-%d %H:%M"))
                return {
                    "sonraki_vakit": "imsak",
                    "vakit": yarin_imsak_str,
                    "kalan_sure": int((vakit_zamani - simdi).total_seconds()),
                    "timezone": timezone_str
                }
            except ValueError:
                pass
                
        return None

    @staticmethod
    def get_vakitler_range(sehir, country_code, start_date, end_date, db_session=None):
        """
        Belirli bir tarih aralığındaki vakitleri döner.
        """
        if db_session is None:
            db_session = db.session
            
        try:
            vakitler = db_session.query(EzanVakti).filter(
                EzanVakti.sehir == sehir,
                EzanVakti.country_code == country_code,
                EzanVakti.tarih >= start_date,
                EzanVakti.tarih <= end_date
            ).order_by(EzanVakti.tarih).all()
            
            return [{
                "tarih": v.tarih.strftime("%Y-%m-%d"),
                "imsak": v.imsak, "gunes": v.gunes, "ogle": v.ogle,
                "ikindi": v.ikindi, "aksam": v.aksam, "yatsi": v.yatsi
            } for v in vakitler]
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"DB range query error for {sehir}: {e}")
            return []

    @staticmethod
    def _save_to_db(sehir, country_code, timezone_str, tarih_date, vakitler, db_session=None):
        if db_session is None:
            db_session = db.session
            
        try:
            # Mevcut kaydı bul
            existing = db_session.query(EzanVakti).filter_by(
                sehir=sehir, country_code=country_code, tarih=tarih_date
            ).first()

            if existing:
                # Mevcut kaydı güncelle
                existing.timezone = timezone_str
                existing.imsak = vakitler['imsak']
                existing.gunes = vakitler['gunes']
                existing.ogle = vakitler['ogle']
                existing.ikindi = vakitler['ikindi']
                existing.aksam = vakitler['aksam']
                existing.yatsi = vakitler['yatsi']
            else:
                # Yeni kayıt ekle
                yeni_vakit = EzanVakti(
                    sehir=sehir, country_code=country_code, timezone=timezone_str, tarih=tarih_date,
                    imsak=vakitler['imsak'], gunes=vakitler['gunes'],
                    ogle=vakitler['ogle'], ikindi=vakitler['ikindi'],
                    aksam=vakitler['aksam'], yatsi=vakitler['yatsi']
                )
                db_session.add(yeni_vakit)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            from flask import current_app
            current_app.logger.error(f"DB save error for {sehir}: {e}")

    @staticmethod
    def _get_from_aladhan(sehir, country_code, tarih_dt):
        """Aladhan API'den vakitleri çeker."""
        try:
            tarih_str = tarih_dt.strftime("%d-%m-%Y")
            # Aladhan API URL (Method 13 = Diyanet)
            # Not: Bazı şehirler için ülke kodu zorunludur.
            url = f"https://api.aladhan.com/v1/timingsByCity/{tarih_str}"
            params = {
                "city": sehir,
                "country": country_code,
                "method": 13
            }
            # Debug için log eklenebilir
            # print(f"Aladhan API Request: {url} params: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                timings = data.get("data", {}).get("timings", {})
                if timings:
                    return {
                        "imsak": timings.get("Fajr"),
                        "gunes": timings.get("Sunrise"),
                        "ogle": timings.get("Dhuhr"),
                        "ikindi": timings.get("Asr"),
                        "aksam": timings.get("Maghrib"),
                        "yatsi": timings.get("Isha")
                    }
            else:
                from flask import current_app
                current_app.logger.error(f"Aladhan API Error for {sehir}: {response.status_code} - {response.text}")
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Aladhan API exception for {sehir}: {e}")
        return None

    @staticmethod
    def _get_from_diyanet(sehir, tarih_dt):
        """Diyanet API simülasyonu."""
        return None


@cache.cached(timeout=86400, key_prefix='daily_content')
def get_daily_content():
    """Günün içeriğini döndürür (Rastgele ve Tekrarsız)."""
    try:
        # 1. Hiç gösterilmemiş olanları getir
        content = DailyContent.query.filter_by(category='daily', is_active=True, last_shown=None).order_by(db.func.random()).first()
        
        # 2. Eğer hepsi gösterildiyse (elimizdekiler bittiyse), en eski gösterileni getir (sıfırla)
        if not content:
            content = DailyContent.query.filter_by(category='daily', is_active=True).order_by(DailyContent.last_shown.asc(), db.func.random()).first()
        
        if content:
            # Gösterilme tarihini güncelle
            content.last_shown = datetime.now().date()
            db.session.commit()
            return content.to_dict()
        
        # Yedek içerik
        return {
            "type": "hadis",
            "text": "Cennet'in sekiz kapısından biri 'Reyyan' adını taşır ki, buradan ancak oruçlular girer.",
            "source": "Buhârî, Savm, 4"
        }
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.error(f"Daily content error: {e}")
        return {
            "type": "hadis",
            "text": "Cennet'in sekiz kapısından biri 'Reyyan' adını taşır ki, buradan ancak oruçlular girer.",
            "source": "Buhârî, Savm, 4"
        }

def get_guides():
    """Tüm bilgi köşesi yazılarını veritabanından döndürür."""
    try:
        guides = Guide.query.filter_by(is_active=True).order_by(Guide.updated_at.desc()).all()
        return [guide.to_dict() for guide in guides]
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Get guides error: {e}")
    return []

def get_guide_by_slug(slug):
    """Slug'a göre tek bir bilgi köşesi yazısı veritabanından döndürür."""
    try:
        guide = Guide.query.filter_by(slug=slug, is_active=True).first()
        if guide:
            return guide.to_dict()
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Get guide by slug error: {e}")
    return None
