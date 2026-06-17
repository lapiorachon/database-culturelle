"""
=============================================================================
 COCKPIT MULTIMÉDIA - Application de gestion de collection (Livres, Mangas,
 BD, Films, Séries, Animes) connectée nativement à PostgreSQL.
 Thème "Racing" sombre et agressif. Multi-utilisateurs avec collection
 commune + listes personnelles.
=============================================================================
"""
 
import base64
import os
import re
import time
from datetime import date, datetime, timedelta
 
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st
 
try:
    import plotly.express as px
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
 
 
# =============================================================================
# 1. CONFIGURATION GÉNÉRALE DE LA PAGE
# =============================================================================
 
st.set_page_config(
    page_title="Cockpit Multimédia",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
STATUTS = ["PAL", "En cours", "Bibliothèque", "Abandonné"]
TYPES_MEDIA = ["Livre", "Livre numérique", "Manga", "BD/Comics", "Film", "Série", "Anime"]
LANGUES = ["Français", "Anglais", "Japonais", "Coréen", "Espagnol", "Autre"]
 
# Pour chaque type de média : (label affiché du champ quantité, unité courte)
# Cela permet d'adapter dynamiquement le formulaire ET de calculer les stats
# cumulées (durée totale des films, épisodes totaux, pages totales, etc.)
QUANTITE_PAR_TYPE = {
    "Livre": ("Nombre de pages", "pages"),
    "BD/Comics": ("Nombre de pages", "pages"),
    "Manga": ("Nombre de pages", "pages"),
    "Livre numérique": ("Nombre de chapitres", "chapitres"),
    "Film": ("Durée (en minutes)", "min"),
    "Série": ("Nombre d'épisodes", "épisodes"),
    "Anime": ("Nombre d'épisodes", "épisodes"),
}
 
# Intervalle (en secondes) de la synchronisation automatique en arrière-plan.
AUTO_SYNC_INTERVAL = 25
 
 
# =============================================================================
# 2. THÈME "RACING" — CSS INJECTÉ
# =============================================================================
 
RACING_CSS = """
<style>
    /* Fond général sombre */
    .stApp {
        background: radial-gradient(circle at top left, #1a1a1a 0%, #0a0a0a 60%);
        color: #ff4d47;
    }
 
    /* Force la couleur rouge sur les éléments de texte courants de Streamlit */
    p, span, label, .stMarkdown, .stCaption, div[data-testid="stMetricValue"],
    div[data-testid="stMetricLabel"], .stText {
        color: #ff4d47 !important;
    }
 
    /* Police plus agressive pour les titres */
    h1, h2, h3 {
        font-family: 'Arial Black', 'Helvetica Neue', sans-serif;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
 
    h1 {
        color: #ffffff;
        text-shadow: 0 0 8px #e10600, 0 0 18px rgba(225, 6, 0, 0.5);
    }
 
    /* Bandeau de tête type "drapeau à damier" */
    .cockpit-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: linear-gradient(90deg, #111111 0%, #1c1c1c 100%);
        border-bottom: 3px solid #e10600;
        padding: 14px 22px;
        border-radius: 10px;
        margin-bottom: 18px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.6);
    }
 
    .cockpit-title {
        font-size: 28px;
        font-weight: 900;
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
 
    /* Badge de synchronisation lumineux */
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(0, 230, 118, 0.12);
        border: 1px solid #00e676;
        color: #00e676;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 1px;
        text-transform: uppercase;
        box-shadow: 0 0 10px rgba(0, 230, 118, 0.55);
        animation: pulseGlow 1.8s infinite;
    }
 
    .live-dot {
        width: 9px;
        height: 9px;
        background: #00e676;
        border-radius: 50%;
        box-shadow: 0 0 6px #00e676;
    }
 
    .live-badge-error {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(225, 6, 0, 0.12);
        border: 1px solid #e10600;
        color: #ff5b50;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
 
    @keyframes pulseGlow {
        0%   { box-shadow: 0 0 6px rgba(0, 230, 118, 0.4); }
        50%  { box-shadow: 0 0 16px rgba(0, 230, 118, 0.9); }
        100% { box-shadow: 0 0 6px rgba(0, 230, 118, 0.4); }
    }
 
    /* Cartes d'œuvres */
    .media-card {
        background: linear-gradient(160deg, #181818 0%, #101010 100%);
        border: 1px solid #2b2b2b;
        border-left: 4px solid #e10600;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        transition: 0.2s;
    }
    .media-card:hover {
        border-left: 4px solid #00e676;
        box-shadow: 0 0 14px rgba(0,0,0,0.5);
    }
 
    /* Boutons */
    .stButton > button {
        background: linear-gradient(180deg, #e10600 0%, #a30400 100%);
        color: #ffffff;
        border: none;
        border-radius: 6px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        transition: 0.15s;
    }
    .stButton > button:hover {
        background: linear-gradient(180deg, #ff1a14 0%, #c30500 100%);
        box-shadow: 0 0 12px rgba(225,6,0,0.6);
    }
 
    /* Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #161616;
        border-radius: 8px 8px 0 0;
        padding: 8px 18px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e10600 !important;
        color: white !important;
    }
 
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d0d 0%, #161616 100%);
        border-right: 2px solid #e10600;
    }
</style>
"""
 
st.markdown(RACING_CSS, unsafe_allow_html=True)
 
 
# =============================================================================
# 3. CONNEXION POSTGRESQL — SÉCURISÉE & RÉSILIENTE
# =============================================================================
 
def get_connection_params():
    """
    Récupère les paramètres de connexion PostgreSQL depuis les variables
    d'environnement / st.secrets.
 
    Compatible avec :
      - Neon / Supabase via une URL complète DATABASE_URL
      - Google Cloud SQL via host/port/dbname/user/password séparés
    """
    database_url = os.environ.get("DATABASE_URL") or st.secrets.get("DATABASE_URL", None)
    if database_url:
        return {"dsn": database_url}
 
    return {
        "host": os.environ.get("PGHOST") or st.secrets.get("PGHOST", ""),
        "port": os.environ.get("PGPORT") or st.secrets.get("PGPORT", "5432"),
        "dbname": os.environ.get("PGDATABASE") or st.secrets.get("PGDATABASE", ""),
        "user": os.environ.get("PGUSER") or st.secrets.get("PGUSER", ""),
        "password": os.environ.get("PGPASSWORD") or st.secrets.get("PGPASSWORD", ""),
        "sslmode": os.environ.get("PGSSLMODE") or st.secrets.get("PGSSLMODE", "require"),
    }
 
 
def open_connection():
    """
    Ouvre une nouvelle connexion PostgreSQL avec autocommit activé.
    Lève l'exception brute en cas d'échec (interceptée plus haut).
    """
    params = get_connection_params()
    if "dsn" in params:
        conn = psycopg2.connect(params["dsn"])
    else:
        conn = psycopg2.connect(
            host=params["host"],
            port=params["port"],
            dbname=params["dbname"],
            user=params["user"],
            password=params["password"],
            sslmode=params.get("sslmode", "require"),
        )
    conn.autocommit = True  # Autocommit activé : pas de gel de données après écriture.
    return conn
 
 
def get_db_connection():
    """
    Retourne une connexion PostgreSQL valide, stockée en session_state.
    Si la connexion existante est morte, elle est recréée automatiquement.
    """
    conn = st.session_state.get("_pg_conn")
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            st.session_state["_pg_conn"] = None
 
    new_conn = open_connection()
    st.session_state["_pg_conn"] = new_conn
    return new_conn
 
 
def _executer_sans_bloquer(cur, sql: str):
    """
    Exécute une instruction SQL d'initialisation sans jamais faire planter
    l'application : si la table/séquence/colonne existe déjà (cas d'un
    redémarrage ou d'une double exécution du script), l'erreur est avalée
    silencieusement plutôt que de remonter jusqu'à l'écran.
    """
    try:
        cur.execute(sql)
    except Exception:
        # Conflit bénin (objet déjà existant) : on l'ignore et on continue.
        cur.connection.rollback()
 
 
def init_database():
    """
    Crée les tables nécessaires si elles n'existent pas, et ajoute les
    colonnes 'date_debut' / 'date_fin' si elles sont absentes (ALTER TABLE
    ... ADD COLUMN IF NOT EXISTS) afin de ne jamais faire crasher l'app,
    même si cette fonction est appelée plusieurs fois (redémarrages,
    rechargements multiples, etc.).
    """
    conn = get_db_connection()
    with conn.cursor() as cur:
        _executer_sans_bloquer(cur, """
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id SERIAL PRIMARY KEY,
                nom TEXT UNIQUE NOT NULL,
                cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
 
        _executer_sans_bloquer(cur, """
            CREATE TABLE IF NOT EXISTS oeuvres (
                id SERIAL PRIMARY KEY,
                titre TEXT NOT NULL,
                type_media TEXT NOT NULL,
                auteur TEXT,
                saga TEXT,
                saison_tome TEXT,
                genre TEXT,
                pages_episodes TEXT,
                image_url TEXT,
                commentaire TEXT,
                statut TEXT NOT NULL DEFAULT 'PAL',
                note INTEGER,
                proprietaire TEXT,
                cree_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modifie_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
 
        # Ajout résilient des colonnes de dates si elles manquent encore.
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS date_debut DATE;")
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS date_fin DATE;")
 
        # Nouvelles colonnes : langue, piment (contenu sexuel/érotique),
        # plateforme de visionnage/lecture, quantité numérique (pages,
        # épisodes, minutes, chapitres selon le type de média), et image
        # uploadée directement (en plus de l'URL).
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS langue TEXT;")
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS piment INTEGER;")
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS plateforme TEXT;")
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS quantite INTEGER;")
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS image_data TEXT;")
 
        # Marqueur "Je recommande" — coché lors du transfert vers la Bibliothèque.
        _executer_sans_bloquer(cur, "ALTER TABLE oeuvres ADD COLUMN IF NOT EXISTS recommande BOOLEAN DEFAULT FALSE;")
 
        # Affiche personnalisée par saga (indépendante des tomes individuels).
        # Si aucune entrée n'existe pour une saga, l'affiche du dernier tome
        # ajouté est utilisée automatiquement à l'affichage.
        _executer_sans_bloquer(cur, """
            CREATE TABLE IF NOT EXISTS affiches_saga (
                saga TEXT PRIMARY KEY,
                image_url TEXT,
                image_data TEXT,
                modifie_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
 
    conn.commit()  # db.commit() explicite, même si autocommit est actif.
 
 
# =============================================================================
# 4. FONCTIONS D'ACCÈS AUX DONNÉES (CRUD)
# =============================================================================
 
def fetch_oeuvres(statut=None):
    """Récupère les œuvres, éventuellement filtrées par statut."""
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if statut:
            cur.execute(
                "SELECT * FROM oeuvres WHERE statut = %s ORDER BY modifie_le DESC;",
                (statut,),
            )
        else:
            cur.execute("SELECT * FROM oeuvres ORDER BY modifie_le DESC;")
        rows = cur.fetchall()
    return [dict(r) for r in rows]
 
 
def insert_oeuvre(data: dict):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO oeuvres
                (titre, type_media, auteur, saga, saison_tome, genre,
                 pages_episodes, image_url, image_data, commentaire, statut, note,
                 proprietaire, date_debut, date_fin, langue, piment,
                 plateforme, quantite, recommande, modifie_le)
            VALUES
                (%(titre)s, %(type_media)s, %(auteur)s, %(saga)s, %(saison_tome)s,
                 %(genre)s, %(pages_episodes)s, %(image_url)s, %(image_data)s, %(commentaire)s,
                 %(statut)s, %(note)s, %(proprietaire)s, %(date_debut)s,
                 %(date_fin)s, %(langue)s, %(piment)s, %(plateforme)s,
                 %(quantite)s, %(recommande)s, CURRENT_TIMESTAMP);
            """,
            data,
        )
    conn.commit()
 
 
def update_oeuvre(oeuvre_id: int, data: dict):
    conn = get_db_connection()
    data = dict(data)
    data["id"] = oeuvre_id
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE oeuvres SET
                titre = %(titre)s,
                type_media = %(type_media)s,
                auteur = %(auteur)s,
                saga = %(saga)s,
                saison_tome = %(saison_tome)s,
                genre = %(genre)s,
                pages_episodes = %(pages_episodes)s,
                image_url = %(image_url)s,
                image_data = %(image_data)s,
                commentaire = %(commentaire)s,
                statut = %(statut)s,
                note = %(note)s,
                date_debut = %(date_debut)s,
                date_fin = %(date_fin)s,
                langue = %(langue)s,
                piment = %(piment)s,
                plateforme = %(plateforme)s,
                quantite = %(quantite)s,
                recommande = %(recommande)s,
                modifie_le = CURRENT_TIMESTAMP
            WHERE id = %(id)s;
            """,
            data,
        )
    conn.commit()
 
 
def update_statut(oeuvre_id: int, nouveau_statut: str):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE oeuvres SET statut = %s, modifie_le = CURRENT_TIMESTAMP WHERE id = %s;",
            (nouveau_statut, oeuvre_id),
        )
    conn.commit()
 
 
def update_statut_avec_date(oeuvre_id: int, nouveau_statut: str, date_debut):
    """Change le statut ET fixe la date de début en même temps (utilisé pour
    le passage PAL -> En cours, où l'utilisateur choisit sa date de début)."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE oeuvres SET statut = %s, date_debut = %s, modifie_le = CURRENT_TIMESTAMP WHERE id = %s;",
            (nouveau_statut, date_debut, oeuvre_id),
        )
    conn.commit()
 
 
def delete_oeuvre(oeuvre_id: int):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM oeuvres WHERE id = %s;", (oeuvre_id,))
    conn.commit()
 
 
def fetch_utilisateurs():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM utilisateurs ORDER BY nom;")
        rows = cur.fetchall()
    return [dict(r) for r in rows]
 
 
def fetch_affiches_saga():
    """Retourne un dictionnaire {nom_de_saga: {image_url, image_data}} pour
    toutes les affiches personnalisées enregistrées."""
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM affiches_saga;")
        rows = cur.fetchall()
    return {r["saga"]: dict(r) for r in rows}
 
 
def set_affiche_saga(saga: str, image_url: str = None, image_data: str = None):
    """Enregistre ou met à jour l'affiche personnalisée d'une saga."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO affiches_saga (saga, image_url, image_data, modifie_le)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (saga) DO UPDATE SET
                image_url = EXCLUDED.image_url,
                image_data = EXCLUDED.image_data,
                modifie_le = CURRENT_TIMESTAMP;
            """,
            (saga, image_url, image_data),
        )
    conn.commit()
 
 
def supprimer_affiche_saga(saga: str):
    """Supprime l'affiche personnalisée d'une saga (retour à l'affiche automatique)."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM affiches_saga WHERE saga = %s;", (saga,))
    conn.commit()
 
 
def creer_utilisateur(nom: str):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO utilisateurs (nom) VALUES (%s) ON CONFLICT (nom) DO NOTHING;",
            (nom,),
        )
    conn.commit()
 
 
# =============================================================================
# 5. UTILITAIRES D'AFFICHAGE
# =============================================================================
 
def format_date_fr(d):
    """Formate une date Python en JJ/MM/AAAA, ou '—' si vide."""
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            return d
    return d.strftime("%d/%m/%Y")
 
 
def afficher_etoiles(note):
    if not note:
        return "Pas encore noté"
    note = int(note)
    return "⭐" * note + "☆" * (5 - note)
 
 
def afficher_piments(piment):
    if not piment:
        return ""
    piment = int(piment)
    return "🌶️" * piment + "⬜" * (5 - piment)
 
 
def minutes_vers_hhmm(total_minutes):
    """Convertit un nombre total de minutes en chaîne 'HHh MMmin'."""
    total_minutes = int(total_minutes or 0)
    heures = total_minutes // 60
    minutes = total_minutes % 60
    return f"{heures}h{minutes:02d}min"
 
 
def get_image_source(oeuvre: dict):
    """Retourne l'image à afficher : priorité à l'image uploadée (base64),
    sinon l'URL fournie, sinon None."""
    if oeuvre.get("image_data"):
        return f"data:image/png;base64,{oeuvre['image_data']}"
    if oeuvre.get("image_url"):
        return oeuvre["image_url"]
    return None
 
 
def get_affiche_saga(saga: str, membres: list, affiches_saga: dict):
    """
    Détermine l'affiche à afficher pour un groupe de saga :
    1. Si une affiche personnalisée a été enregistrée pour cette saga, elle
       est prioritaire.
    2. Sinon, on retombe automatiquement sur l'image du dernier tome ajouté
       (le plus récent par date de création).
    Retourne (source_image_ou_None, a_une_affiche_personnalisee: bool).
    """
    affiche_perso = affiches_saga.get(saga)
    if affiche_perso and (affiche_perso.get("image_data") or affiche_perso.get("image_url")):
        if affiche_perso.get("image_data"):
            return f"data:image/png;base64,{affiche_perso['image_data']}", True
        return affiche_perso["image_url"], True
 
    # Pas d'affiche personnalisée : on prend l'image du tome le plus récent.
    membres_avec_image = [m for m in membres if get_image_source(m)]
    if not membres_avec_image:
        return None, False
    dernier = max(membres_avec_image, key=lambda m: m.get("cree_le") or "")
    return get_image_source(dernier), False
 
 
def _cle_tri_saison_tome(oeuvre: dict):
    """
    Construit une clé de tri 'naturelle' pour le champ saison_tome, afin que
    'Saison 2' se classe bien avant 'Saison 10' (et pas après, comme le
    ferait un tri alphabétique classique). On extrait le premier nombre
    trouvé dans le texte ; à défaut, on retombe sur le texte lui-même.
    """
    texte = (oeuvre.get("saison_tome") or "").strip()
    match = re.search(r"\d+", texte)
    if match:
        return (0, int(match.group()), texte.lower())
    return (1, 0, texte.lower())
 
 
def oeuvre_modifiable(oeuvre: dict) -> bool:
    """
    Retourne True si l'œuvre a été créée il y a moins de 24h, et peut donc
    encore être corrigée librement (faute de frappe, mauvaise info...).
    Passé ce délai, le bouton 'Modifier' disparaît simplement.
    """
    cree_le = oeuvre.get("cree_le")
    if cree_le is None:
        return False
    if isinstance(cree_le, str):
        try:
            cree_le = datetime.strptime(cree_le, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            try:
                cree_le = datetime.strptime(cree_le, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False
    return (datetime.now() - cree_le) < timedelta(hours=24)
 
 
def afficher_carte_oeuvre(oeuvre: dict, afficher_periode: bool = False, dans_groupe: bool = False):
    """Affiche une œuvre sous forme de carte stylisée 'Racing'.
 
    Si dans_groupe=True, la carte est affichée à l'intérieur d'un bloc de
    saga déjà titré : on n'affiche donc pas une seconde fois le nom de la
    saga sur la ligne d'info (déjà visible dans l'en-tête du groupe).
    """
    with st.container():
        st.markdown('<div class="media-card">', unsafe_allow_html=True)
        col_img, col_info, col_actions = st.columns([1, 4, 2])
 
        with col_img:
            image_source = get_image_source(oeuvre)
            if image_source:
                st.image(image_source, width=80)
            else:
                st.markdown("📚")
 
        with col_info:
            titre_ligne = f"**{oeuvre['titre']}**  ·  _{oeuvre['type_media']}_"
            if oeuvre.get("recommande"):
                titre_ligne += "  ❤️ **Recommandé**"
            st.markdown(titre_ligne)
            sous_ligne = []
            if oeuvre.get("auteur"):
                sous_ligne.append(f"✍️ {oeuvre['auteur']}")
            if not dans_groupe and oeuvre.get("saga"):
                sous_ligne.append(f"📖 {oeuvre['saga']}")
            if oeuvre.get("saison_tome"):
                sous_ligne.append(f"🔖 {oeuvre['saison_tome']}")
            if oeuvre.get("genre"):
                sous_ligne.append(f"🎭 {oeuvre['genre']}")
            if oeuvre.get("langue"):
                sous_ligne.append(f"🌐 {oeuvre['langue']}")
            if oeuvre.get("plateforme"):
                sous_ligne.append(f"📺 {oeuvre['plateforme']}")
            if oeuvre.get("quantite"):
                _, unite = QUANTITE_PAR_TYPE.get(oeuvre["type_media"], ("Quantité", ""))
                sous_ligne.append(f"🔢 {oeuvre['quantite']} {unite}")
            if sous_ligne:
                st.caption(" • ".join(sous_ligne))
 
            if oeuvre.get("note"):
                st.markdown(afficher_etoiles(oeuvre["note"]))
 
            if oeuvre.get("piment"):
                st.markdown(afficher_piments(oeuvre["piment"]))
 
            if oeuvre.get("commentaire"):
                st.caption(f"💬 {oeuvre['commentaire']}")
 
            if afficher_periode and (oeuvre.get("date_debut") or oeuvre.get("date_fin")):
                st.markdown(
                    f"🗓️ Période : du **{format_date_fr(oeuvre.get('date_debut'))}** "
                    f"au **{format_date_fr(oeuvre.get('date_fin'))}**"
                )
 
            if oeuvre.get("proprietaire"):
                st.caption(f"👤 {oeuvre['proprietaire']}")
 
        with col_actions:
            cle_base = f"oeuvre_{oeuvre['id']}"
 
            if oeuvre["statut"] == "PAL":
                with st.popover("▶️ Commencer", use_container_width=True):
                    st.caption("Quelle est la date de début ?")
                    date_debut_choisie = st.date_input(
                        "Date de début", value=date.today(), key=f"{cle_base}_date_debut_commencer"
                    )
                    if st.button("✅ Valider", key=f"{cle_base}_valider_commencer", use_container_width=True):
                        update_statut_avec_date(oeuvre["id"], "En cours", date_debut_choisie)
                        st.rerun()
                if st.button("📦 → Bibliothèque", key=f"{cle_base}_transfert", use_container_width=True):
                    st.session_state["dialog_transfert_id"] = oeuvre["id"]
 
            elif oeuvre["statut"] == "En cours":
                if st.button("📦 Terminer", key=f"{cle_base}_terminer", use_container_width=True):
                    st.session_state["dialog_transfert_id"] = oeuvre["id"]
                if st.button("⛔ Abandonner", key=f"{cle_base}_abandon", use_container_width=True):
                    update_statut(oeuvre["id"], "Abandonné")
                    st.rerun()
 
            elif oeuvre["statut"] == "Abandonné":
                if st.button("↩️ Reprendre", key=f"{cle_base}_reprendre", use_container_width=True):
                    update_statut(oeuvre["id"], "En cours")
                    st.rerun()
 
            if st.button("🗑️ Supprimer", key=f"{cle_base}_suppr", use_container_width=True):
                delete_oeuvre(oeuvre["id"])
                st.rerun()
 
            if oeuvre_modifiable(oeuvre):
                if st.button("✏️ Modifier", key=f"{cle_base}_modifier", use_container_width=True):
                    st.session_state["dialog_modification_id"] = oeuvre["id"]
 
        st.markdown("</div>", unsafe_allow_html=True)
 
 
# =============================================================================
# 6. FENÊTRE MODALE — TRANSFERT PAL / EN COURS → BIBLIOTHÈQUE
# =============================================================================
 
@st.dialog("📦 Transfert vers la Bibliothèque", width="large")
def dialog_transfert(oeuvre_id: int):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM oeuvres WHERE id = %s;", (oeuvre_id,))
        oeuvre = cur.fetchone()
 
    if oeuvre is None:
        st.error("Cette œuvre n'existe plus.")
        return
 
    oeuvre = dict(oeuvre)
 
    col1, col2 = st.columns(2, gap="large")
 
    with col1:
        titre = st.text_input("Titre", value=oeuvre.get("titre") or "")
        saga = st.text_input("Saga", value=oeuvre.get("saga") or "")
        saison_tome = st.text_input("Saison / Tome", value=oeuvre.get("saison_tome") or "")
        plateforme = st.text_input(
            "Plateforme (Netflix, Disney+, Kindle, papier...)",
            value=oeuvre.get("plateforme") or "",
        )
        date_debut = st.date_input(
            "Date de début",
            value=oeuvre.get("date_debut") or date.today(),
        )
 
    with col2:
        genre = st.text_input("Genre", value=oeuvre.get("genre") or "")
        note = st.slider("Note / Avis (étoiles)", min_value=0, max_value=5, value=oeuvre.get("note") or 0)
        piment = st.slider("🌶️ Piment (contenu sexuel/érotique)", min_value=0, max_value=5, value=oeuvre.get("piment") or 0)
        commentaire = st.text_area("Commentaire", value=oeuvre.get("commentaire") or "")
        date_fin = st.date_input(
            "Date de fin",
            value=oeuvre.get("date_fin") or date.today(),
        )
        recommande = st.checkbox("❤️ Je recommande cette œuvre", value=bool(oeuvre.get("recommande")))
 
    st.markdown("---")
    col_spacer, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("✅ Valider le transfert", type="primary", use_container_width=True):
            update_oeuvre(
                oeuvre_id,
                {
                    "titre": titre,
                    "type_media": oeuvre.get("type_media"),
                    "auteur": oeuvre.get("auteur"),
                    "saga": saga,
                    "saison_tome": saison_tome,
                    "genre": genre,
                    "pages_episodes": oeuvre.get("pages_episodes"),
                    "image_url": oeuvre.get("image_url"),
                    "image_data": oeuvre.get("image_data"),
                    "commentaire": commentaire,
                    "statut": "Bibliothèque",
                    "note": note if note > 0 else None,
                    "piment": piment if piment > 0 else None,
                    "date_debut": date_debut,
                    "date_fin": date_fin,
                    "langue": oeuvre.get("langue"),
                    "plateforme": plateforme or None,
                    "quantite": oeuvre.get("quantite"),
                    "recommande": recommande,
                },
            )
            st.session_state["dialog_transfert_id"] = None
            st.success("Œuvre transférée vers la Bibliothèque !")
            st.rerun()
 
 
# =============================================================================
# 6bis. FENÊTRE MODALE — MODIFICATION (DANS LES 24H APRÈS CRÉATION)
# =============================================================================
 
@st.dialog("✏️ Modifier l'œuvre", width="large")
def dialog_modification(oeuvre_id: int):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM oeuvres WHERE id = %s;", (oeuvre_id,))
        oeuvre = cur.fetchone()
 
    if oeuvre is None:
        st.error("Cette œuvre n'existe plus.")
        return
 
    oeuvre = dict(oeuvre)
 
    if not oeuvre_modifiable(oeuvre):
        st.warning("Le délai de 24h pour modifier cette œuvre est dépassé.")
        return
 
    st.caption("Tu peux corriger une faute de frappe ou une mauvaise info ci-dessous (modifiable pendant 24h après l'ajout).")
 
    label_quantite, _unite = QUANTITE_PAR_TYPE.get(oeuvre.get("type_media"), ("Quantité", ""))
 
    col1, col2 = st.columns(2, gap="large")
 
    with col1:
        titre = st.text_input("Titre", value=oeuvre.get("titre") or "", key=f"mod_titre_{oeuvre_id}")
        type_media = st.selectbox(
            "Type de média", TYPES_MEDIA,
            index=TYPES_MEDIA.index(oeuvre["type_media"]) if oeuvre.get("type_media") in TYPES_MEDIA else 0,
            key=f"mod_type_{oeuvre_id}",
        )
        auteur = st.text_input("Auteur / Réalisateur / Studio", value=oeuvre.get("auteur") or "", key=f"mod_auteur_{oeuvre_id}")
        saga = st.text_input("Saga / Collection", value=oeuvre.get("saga") or "", key=f"mod_saga_{oeuvre_id}")
        saison_tome = st.text_input("Saison / Tome", value=oeuvre.get("saison_tome") or "", key=f"mod_saison_{oeuvre_id}")
        genre = st.text_input("Genre", value=oeuvre.get("genre") or "", key=f"mod_genre_{oeuvre_id}")
        langue = st.selectbox(
            "Langue", LANGUES,
            index=LANGUES.index(oeuvre["langue"]) if oeuvre.get("langue") in LANGUES else 0,
            key=f"mod_langue_{oeuvre_id}",
        )
 
    with col2:
        plateforme = st.text_input("Plateforme", value=oeuvre.get("plateforme") or "", key=f"mod_plateforme_{oeuvre_id}")
        quantite = st.number_input(label_quantite, min_value=0, step=1, value=int(oeuvre.get("quantite") or 0), key=f"mod_quantite_{oeuvre_id}")
        commentaire = st.text_area("Commentaire / Avis", value=oeuvre.get("commentaire") or "", key=f"mod_commentaire_{oeuvre_id}")
        image_url = st.text_input("URL de l'image de couverture", value=oeuvre.get("image_url") or "", key=f"mod_image_url_{oeuvre_id}")
        image_upload = st.file_uploader(
            "...ou remplace par une image depuis ton appareil",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"mod_image_upload_{oeuvre_id}",
        )
 
    if oeuvre["statut"] in ("Bibliothèque",):
        st.markdown("---")
        col3, col4 = st.columns(2)
        with col3:
            date_debut = st.date_input("Date de début", value=oeuvre.get("date_debut") or date.today(), key=f"mod_date_debut_{oeuvre_id}")
            note = st.slider("Note / Avis (étoiles)", min_value=0, max_value=5, value=oeuvre.get("note") or 0, key=f"mod_note_{oeuvre_id}")
        with col4:
            date_fin = st.date_input("Date de fin", value=oeuvre.get("date_fin") or date.today(), key=f"mod_date_fin_{oeuvre_id}")
            piment = st.slider("🌶️ Piment", min_value=0, max_value=5, value=oeuvre.get("piment") or 0, key=f"mod_piment_{oeuvre_id}")
        recommande = st.checkbox("❤️ Je recommande cette œuvre", value=bool(oeuvre.get("recommande")), key=f"mod_recommande_{oeuvre_id}")
    else:
        date_debut = oeuvre.get("date_debut")
        date_fin = oeuvre.get("date_fin")
        note = oeuvre.get("note")
        piment = oeuvre.get("piment")
        recommande = oeuvre.get("recommande")
 
    st.markdown("---")
    col_spacer, col_btn = st.columns([3, 1])
    with col_btn:
        if st.button("✅ Enregistrer", type="primary", use_container_width=True, key=f"mod_valider_{oeuvre_id}"):
            image_data_b64 = oeuvre.get("image_data")
            if image_upload is not None:
                image_data_b64 = base64.b64encode(image_upload.read()).decode("utf-8")
 
            update_oeuvre(
                oeuvre_id,
                {
                    "titre": titre,
                    "type_media": type_media,
                    "auteur": auteur or None,
                    "saga": saga or None,
                    "saison_tome": saison_tome or None,
                    "genre": genre or None,
                    "pages_episodes": oeuvre.get("pages_episodes"),
                    "image_url": image_url or None,
                    "image_data": image_data_b64,
                    "commentaire": commentaire or None,
                    "statut": oeuvre["statut"],
                    "note": note if note and note > 0 else None,
                    "piment": piment if piment and piment > 0 else None,
                    "date_debut": date_debut,
                    "date_fin": date_fin,
                    "langue": langue or None,
                    "plateforme": plateforme or None,
                    "quantite": int(quantite) if quantite else None,
                    "recommande": recommande,
                },
            )
            st.session_state["dialog_modification_id"] = None
            st.success("Modifications enregistrées !")
            st.rerun()
 
 
# =============================================================================
# 7. FORMULAIRE D'AJOUT D'UNE NOUVELLE ŒUVRE
# =============================================================================
 
def formulaire_ajout(proprietaire_defaut: str):
    with st.expander("➕ Ajouter une nouvelle œuvre", expanded=False):
        # Le type de média ET le statut initial doivent être choisis EN
        # DEHORS du st.form pour pouvoir adapter dynamiquement le formulaire
        # (label de quantité selon le type, et apparition des champs
        # "Bibliothèque" — note, piment, dates, recommandation — uniquement
        # si on encode directement une œuvre terminée). Les st.form
        # n'autorisent pas de rerun immédiat sur un changement de champ interne.
        col_type, col_statut = st.columns(2)
        with col_type:
            type_media = st.selectbox("Type de média *", TYPES_MEDIA, key="type_media_ajout")
        with col_statut:
            statut_initial = st.selectbox("Statut initial", STATUTS, key="statut_initial_ajout")
 
        label_quantite, _unite = QUANTITE_PAR_TYPE.get(type_media, ("Quantité", ""))
        directement_termine = statut_initial == "Bibliothèque"
 
        with st.form("form_ajout_oeuvre", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                titre = st.text_input("Titre *")
                auteur = st.text_input("Auteur / Réalisateur / Studio")
                saga = st.text_input("Saga / Collection")
                saison_tome = st.text_input("Saison / Tome")
                genre = st.text_input("Genre")
                langue = st.selectbox("Langue", LANGUES)
            with col2:
                plateforme = st.text_input("Plateforme (Netflix, Kindle, Wattpad, papier...)")
                quantite = st.number_input(label_quantite, min_value=0, step=1, value=0)
                image_url = st.text_input("URL de l'image de couverture (optionnel)")
                image_upload = st.file_uploader(
                    "...ou charge une image depuis ton appareil",
                    type=["png", "jpg", "jpeg", "webp"],
                )
                commentaire = st.text_area("Commentaire / Avis")
 
            # --- Champs supplémentaires, visibles uniquement si l'œuvre est
            # ajoutée directement comme terminée (statut = Bibliothèque) ---
            note = 0
            piment = 0
            recommande = False
            date_debut_saisie = date.today()
            date_fin_saisie = date.today()
 
            if directement_termine:
                st.markdown("---")
                st.markdown("**📚 Détails de fin (puisque l'œuvre est directement en Bibliothèque)**")
                col3, col4 = st.columns(2)
                with col3:
                    date_debut_saisie = st.date_input("Date de début", value=date.today())
                    note = st.slider("Note / Avis (étoiles)", min_value=0, max_value=5, value=0)
                with col4:
                    date_fin_saisie = st.date_input("Date de fin", value=date.today())
                    piment = st.slider("🌶️ Piment (contenu sexuel/érotique)", min_value=0, max_value=5, value=0)
                recommande = st.checkbox("❤️ Je recommande cette œuvre")
 
            submitted = st.form_submit_button("🏁 Ajouter à la collection", use_container_width=True)
 
            if submitted:
                if not titre.strip():
                    st.warning("Le titre est obligatoire.")
                else:
                    image_data_b64 = None
                    if image_upload is not None:
                        image_data_b64 = base64.b64encode(image_upload.read()).decode("utf-8")
 
                    if directement_termine:
                        date_debut_finale = date_debut_saisie
                        date_fin_finale = date_fin_saisie
                    elif statut_initial != "PAL":
                        date_debut_finale = date.today()
                        date_fin_finale = None
                    else:
                        date_debut_finale = None
                        date_fin_finale = None
 
                    insert_oeuvre({
                        "titre": titre.strip(),
                        "type_media": type_media,
                        "auteur": auteur or None,
                        "saga": saga or None,
                        "saison_tome": saison_tome or None,
                        "genre": genre or None,
                        "pages_episodes": None,
                        "image_url": image_url or None,
                        "image_data": image_data_b64,
                        "commentaire": commentaire or None,
                        "statut": statut_initial,
                        "note": note if note > 0 else None,
                        "piment": piment if piment > 0 else None,
                        "proprietaire": proprietaire_defaut,
                        "date_debut": date_debut_finale,
                        "date_fin": date_fin_finale,
                        "langue": langue or None,
                        "plateforme": plateforme or None,
                        "quantite": int(quantite) if quantite else None,
                        "recommande": recommande,
                    })
                    st.success(f"« {titre} » a été ajouté !")
                    st.rerun()
 
 
# =============================================================================
# 8. ONGLET TABLEAU DE BORD (STATS & GRAPHIQUES)
# =============================================================================
 
def onglet_tableau_de_bord(toutes_oeuvres: list):
    st.subheader("📊 Tableau de bord de la collection")
 
    if not toutes_oeuvres:
        st.info("Aucune œuvre enregistrée pour le moment. Ajoute ta première œuvre ci-dessus !")
        return
 
    df = pd.DataFrame(toutes_oeuvres)
 
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Total œuvres", len(df))
    col2.metric("✅ Terminées", int((df["statut"] == "Bibliothèque").sum()))
    col3.metric("▶️ En cours", int((df["statut"] == "En cours").sum()))
    col4.metric("⏳ En attente (PAL)", int((df["statut"] == "PAL").sum()))
 
    st.markdown("---")
    col_a, col_b = st.columns(2)
 
    with col_a:
        st.markdown("**Répartition par statut**")
        repartition_statut = df["statut"].value_counts().reset_index()
        repartition_statut.columns = ["Statut", "Nombre"]
        if PLOTLY_OK:
            fig = px.pie(
                repartition_statut, names="Statut", values="Nombre", hole=0.45,
                color_discrete_sequence=["#e10600", "#ff8a00", "#00e676", "#555555"],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f5f5f5",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(repartition_statut.set_index("Statut"))
 
    with col_b:
        st.markdown("**Répartition par type de média**")
        repartition_type = df["type_media"].value_counts().reset_index()
        repartition_type.columns = ["Type", "Nombre"]
        if PLOTLY_OK:
            fig2 = px.bar(
                repartition_type, x="Type", y="Nombre",
                color="Type",
                color_discrete_sequence=px.colors.sequential.Reds,
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f5f5f5",
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.bar_chart(repartition_type.set_index("Type"))
 
    if "langue" in df.columns and df["langue"].notna().any():
        st.markdown("---")
        st.markdown("**🌐 Répartition par langue**")
        df_langue = df[df["langue"].notna() & (df["langue"] != "")]
        repartition_langue = df_langue["langue"].value_counts().reset_index()
        repartition_langue.columns = ["Langue", "Nombre"]
        if PLOTLY_OK:
            fig_langue = px.pie(
                repartition_langue, names="Langue", values="Nombre", hole=0.45,
                color_discrete_sequence=px.colors.sequential.Reds_r,
            )
            fig_langue.update_traces(textinfo="percent+label")
            fig_langue.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f5f5f5",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_langue, use_container_width=True)
        else:
            st.bar_chart(repartition_langue.set_index("Langue"))
 
    if "note" in df.columns and df["note"].notna().any():
        st.markdown("---")
        st.markdown("**Distribution des notes (œuvres terminées)**")
        df_notes = df[df["note"].notna()]
        if PLOTLY_OK:
            fig3 = px.histogram(
                df_notes, x="note", nbins=5,
                color_discrete_sequence=["#e10600"],
            )
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f5f5f5",
                xaxis_title="Note (étoiles)",
                yaxis_title="Nombre d'œuvres",
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.bar_chart(df_notes["note"].value_counts().sort_index())
 
    if "proprietaire" in df.columns and df["proprietaire"].notna().any():
        st.markdown("---")
        st.markdown("**Contributions par utilisateur**")
        repartition_user = df["proprietaire"].value_counts().reset_index()
        repartition_user.columns = ["Utilisateur", "Nombre"]
        st.dataframe(repartition_user, use_container_width=True, hide_index=True)
 
    # --- Statistiques cumulées par type de média (sur les œuvres terminées) ---
    st.markdown("---")
    st.markdown("**📈 Cumuls par type de média (œuvres terminées)**")
 
    df_termine = df[df["statut"] == "Bibliothèque"].copy()
    if "quantite" in df_termine.columns:
        df_termine["quantite"] = pd.to_numeric(df_termine["quantite"], errors="coerce").fillna(0)
    else:
        df_termine["quantite"] = 0
 
    col_films, col_series, col_livres_num, col_livres_papier = st.columns(4)
 
    with col_films:
        minutes_films = df_termine.loc[df_termine["type_media"] == "Film", "quantite"].sum()
        st.metric("🎬 Temps cumulé Films", minutes_vers_hhmm(minutes_films))
 
    with col_series:
        episodes_series = df_termine.loc[
            df_termine["type_media"].isin(["Série", "Anime"]), "quantite"
        ].sum()
        st.metric("📺 Épisodes cumulés Séries/Animes", int(episodes_series))
 
    with col_livres_num:
        chapitres_num = df_termine.loc[df_termine["type_media"] == "Livre numérique", "quantite"].sum()
        st.metric("📱 Chapitres cumulés (Wattpad, Webtoon...)", int(chapitres_num))
 
    with col_livres_papier:
        pages_papier = df_termine.loc[
            df_termine["type_media"].isin(["Livre", "BD/Comics", "Manga"]), "quantite"
        ].sum()
        st.metric("📖 Pages cumulées Livres/BD/Mangas", int(pages_papier))
 
 
# =============================================================================
# 9. ONGLET PAR STATUT (AVEC FILTRES)
# =============================================================================
 
def onglet_statut(statut: str, toutes_oeuvres: list):
    oeuvres_du_statut = [o for o in toutes_oeuvres if o["statut"] == statut]
 
    with st.expander("🔍 Filtres", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            filtre_type = st.multiselect(
                "Type de média", TYPES_MEDIA, key=f"filtre_type_{statut}"
            )
        with col2:
            proprietaires_dispo = sorted({
                o["proprietaire"] for o in oeuvres_du_statut if o.get("proprietaire")
            })
            filtre_user = st.multiselect(
                "Utilisateur", proprietaires_dispo, key=f"filtre_user_{statut}"
            )
        with col3:
            filtre_recherche = st.text_input(
                "Recherche par titre", key=f"filtre_recherche_{statut}"
            )
 
        filtre_recommande = False
        if statut == "Bibliothèque":
            filtre_recommande = st.checkbox(
                "❤️ Recommandées uniquement", key=f"filtre_recommande_{statut}"
            )
 
    resultat = oeuvres_du_statut
    if filtre_type:
        resultat = [o for o in resultat if o["type_media"] in filtre_type]
    if filtre_user:
        resultat = [o for o in resultat if o.get("proprietaire") in filtre_user]
    if filtre_recherche:
        resultat = [
            o for o in resultat
            if filtre_recherche.lower() in (o["titre"] or "").lower()
        ]
    if filtre_recommande:
        resultat = [o for o in resultat if o.get("recommande")]
 
    st.caption(f"{len(resultat)} œuvre(s) affichée(s) sur {len(oeuvres_du_statut)} au total")
 
    if not resultat:
        st.info("Aucune œuvre ne correspond à ces critères dans cette section.")
        return
 
    afficher_periode = statut == "Bibliothèque"
 
    # --- Regroupement par saga ---
    # Les œuvres qui partagent le même nom de saga (non vide) sont
    # regroupées sous un même bloc dépliable, triées par saison/tome.
    # Les œuvres sans saga renseignée restent affichées individuellement.
    groupes_saga = {}
    oeuvres_isolees = []
    for oeuvre in resultat:
        saga = (oeuvre.get("saga") or "").strip()
        if saga:
            groupes_saga.setdefault(saga, []).append(oeuvre)
        else:
            oeuvres_isolees.append(oeuvre)
 
    affiches_saga = fetch_affiches_saga()
 
    # Affichage des groupes de saga, triés alphabétiquement.
    for saga in sorted(groupes_saga.keys(), key=str.lower):
        membres = sorted(groupes_saga[saga], key=_cle_tri_saison_tome)
        nb = len(membres)
        libelle_nb = f"{nb} élément{'s' if nb > 1 else ''}"
 
        source_affiche, est_personnalisee = get_affiche_saga(saga, membres, affiches_saga)
 
        col_affiche, col_groupe = st.columns([1, 6])
        with col_affiche:
            if source_affiche:
                st.image(source_affiche, width=90)
            else:
                st.markdown("📖")
            with st.popover("🖼️ Modifier l'affiche", use_container_width=True):
                st.caption(f"Affiche de la saga « {saga} »")
                nouvelle_url = st.text_input(
                    "URL de l'image", key=f"affiche_url_{statut}_{saga}"
                )
                nouvel_upload = st.file_uploader(
                    "...ou charge une image depuis ton appareil",
                    type=["png", "jpg", "jpeg", "webp"],
                    key=f"affiche_upload_{statut}_{saga}",
                )
                col_valider, col_reset = st.columns(2)
                with col_valider:
                    if st.button("✅ Valider", key=f"affiche_valider_{statut}_{saga}", use_container_width=True):
                        image_data_b64 = None
                        if nouvel_upload is not None:
                            image_data_b64 = base64.b64encode(nouvel_upload.read()).decode("utf-8")
                        set_affiche_saga(
                            saga,
                            image_url=nouvelle_url or None,
                            image_data=image_data_b64,
                        )
                        st.success("Affiche mise à jour !")
                        st.rerun()
                with col_reset:
                    if est_personnalisee and st.button(
                        "↩️ Auto", key=f"affiche_reset_{statut}_{saga}", use_container_width=True
                    ):
                        supprimer_affiche_saga(saga)
                        st.success("Retour à l'affiche automatique.")
                        st.rerun()
 
        with col_groupe:
            with st.expander(f"📖 **{saga}** — {libelle_nb}", expanded=False):
                for oeuvre in membres:
                    label_tome = oeuvre.get("saison_tome") or oeuvre["titre"]
                    statut_emoji = {
                        "PAL": "⏳", "En cours": "▶️", "Bibliothèque": "✅", "Abandonné": "⛔"
                    }.get(oeuvre["statut"], "")
                    with st.popover(f"🔖 {label_tome}  {statut_emoji}", use_container_width=True):
                        afficher_carte_oeuvre(oeuvre, afficher_periode=afficher_periode, dans_groupe=True)
                        if st.session_state.get("dialog_transfert_id") == oeuvre["id"]:
                            dialog_transfert(oeuvre["id"])
                        if st.session_state.get("dialog_modification_id") == oeuvre["id"]:
                            dialog_modification(oeuvre["id"])
 
    # Affichage des œuvres isolées (sans saga), comme avant.
    for oeuvre in oeuvres_isolees:
        afficher_carte_oeuvre(oeuvre, afficher_periode=afficher_periode)
 
        if st.session_state.get("dialog_transfert_id") == oeuvre["id"]:
            dialog_transfert(oeuvre["id"])
        if st.session_state.get("dialog_modification_id") == oeuvre["id"]:
            dialog_modification(oeuvre["id"])
 
 
# =============================================================================
# 10. FRAGMENT DE SYNCHRONISATION AUTOMATIQUE
# =============================================================================
 
@st.fragment(run_every=AUTO_SYNC_INTERVAL)
def fragment_sync_auto():
    """
    Ce fragment se relance tout seul toutes les AUTO_SYNC_INTERVAL secondes
    pour vérifier qu'on a bien les dernières données (sans recharger toute
    la page). Il pousse juste un petit indicateur d'heure de dernière
    synchro ; le contenu réel est rechargé via fetch_oeuvres() au prochain
    rerun de l'app principale.
    """
    st.session_state["derniere_sync"] = datetime.now().strftime("%H:%M:%S")
    st.caption(f"🔄 Dernière synchro auto : {st.session_state['derniere_sync']}")
 
 
# =============================================================================
# 11. EN-TÊTE DU COCKPIT
# =============================================================================
 
def afficher_entete(connexion_ok: bool):
    badge = (
        '<span class="live-badge"><span class="live-dot"></span> POSTGRES_LIVE_SYNC</span>'
        if connexion_ok else
        '<span class="live-badge-error">⚠️ POSTGRES_LIVE_SYNC — DÉCONNECTÉ</span>'
    )
    st.markdown(
        f"""
        <div class="cockpit-header">
            <div class="cockpit-title">🏎️ Cockpit Multimédia</div>
            <div>{badge}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
 
# =============================================================================
# 12. APPLICATION PRINCIPALE
# =============================================================================
 
def main():
    connexion_ok = False
    try:
        init_database()
        connexion_ok = True
    except Exception as e:
        afficher_entete(connexion_ok=False)
        st.error(f"BASE INDISPONIBLE : {str(e)}")
        st.stop()
 
    afficher_entete(connexion_ok=True)
 
    # --- Sidebar : sélection / création de l'utilisateur ---
    with st.sidebar:
        st.markdown("### 👤 Profil")
        try:
            utilisateurs = fetch_utilisateurs()
        except Exception as e:
            st.error(f"BASE INDISPONIBLE : {str(e)}")
            st.stop()
 
        noms_utilisateurs = [u["nom"] for u in utilisateurs]
 
        choix = st.selectbox(
            "Utilisateur actif",
            options=["— Choisir —"] + noms_utilisateurs + ["➕ Nouvel utilisateur"],
        )
 
        if choix == "➕ Nouvel utilisateur":
            nouveau_nom = st.text_input("Prénom du nouvel utilisateur")
            if st.button("Créer le profil") and nouveau_nom.strip():
                creer_utilisateur(nouveau_nom.strip())
                st.session_state["utilisateur_actif"] = nouveau_nom.strip()
                st.rerun()
        elif choix != "— Choisir —":
            st.session_state["utilisateur_actif"] = choix
 
        utilisateur_actif = st.session_state.get("utilisateur_actif", "Invité")
        st.success(f"Connecté en tant que **{utilisateur_actif}**")
 
        st.markdown("---")
        st.markdown("### 🔄 Synchronisation")
        if st.button("🔁 Actualiser maintenant", use_container_width=True):
            st.rerun()
        fragment_sync_auto()
 
    # --- Récupération des données ---
    try:
        toutes_oeuvres = fetch_oeuvres()
    except Exception as e:
        st.error(f"BASE INDISPONIBLE : {str(e)}")
        st.stop()
 
    # --- Formulaire d'ajout ---
    formulaire_ajout(proprietaire_defaut=utilisateur_actif)
 
    st.markdown("---")
 
    # --- Onglets : 4 statuts + tableau de bord ---
    tab_pal, tab_cours, tab_biblio, tab_abandon, tab_dashboard = st.tabs([
        "⏳ PAL", "▶️ En cours", "📚 Bibliothèque", "⛔ Abandonné", "📊 Tableau de bord"
    ])
 
    with tab_pal:
        onglet_statut("PAL", toutes_oeuvres)
    with tab_cours:
        onglet_statut("En cours", toutes_oeuvres)
    with tab_biblio:
        onglet_statut("Bibliothèque", toutes_oeuvres)
    with tab_abandon:
        onglet_statut("Abandonné", toutes_oeuvres)
    with tab_dashboard:
        onglet_tableau_de_bord(toutes_oeuvres)
 
 
if __name__ == "__main__":
    main()
 
