import itertools, time
from pathlib import Path
import numpy as np
import pandas as pd

from register import Registry, PruebaRegistry

SPLIT, STEAL = 0, 1

registry = Registry()

prueba = PruebaRegistry()

PAYOFF = {
    (SPLIT, SPLIT): (3, 3),
    (SPLIT, STEAL): (0, 5),
    (STEAL, SPLIT): (5, 0),
    (STEAL, STEAL): (1, 1)
}

def play_round(a: int, b: int):
    return PAYOFF[(a, b)]

def play_match(strategy_a, strategy_b, rounds: int = 50, seed: int = 0):
    rng = np.random.default_rng(seed)
    historyA, historyB = [], []   # historiales de jugadas
    pointsA = pointsB = 0       # puntuaciones totales

    for _ in range(rounds):
        # Cada estrategia elige su acción
        a = strategy_a.act(historyA, historyB, rng)
        b = strategy_b.act(historyB, historyA, rng)
        # Se juega la ronda
        resultA, resultB = play_round(a, b)

        # Se guardan datos en strategias
        strategy_a.update_stats(a, resultA)
        strategy_b.update_stats(b, resultB)

        # Se actualizan puntuaciones e historiales
        pointsA += resultA
        pointsB += resultB
        historyA.append(a)
        historyB.append(b)

    return pointsA, pointsB


class League:
    def __init__(self, number, members, rounds, n_ascend_descend):
        self.id = number
        self.members = members  # Dictionary: {name: strategy_object}
        self.strategies = list(members.values())  # List of strategy objects
        self.name_to_index = {name: i for i, name in enumerate(members.keys())}  # Map names to indices in strategies
        self.league_rounds = rounds
        self.n_ascend_descend = n_ascend_descend

        self.clasification = [] #list con tuples (name, points)
        self.result = [] #[{"name": n, "points": p, "position": i + 1}]

    def play(self, season_seed):
        """
        Juega la liga completa (round-robin) y devuelve:
        - table: lista de dicts ordenada por puntos desc (con desempate por nombre)
                 [{"name": str, "points": int, "position": int}, ...]
        - points: dict nombre -> puntos
        """
        rng = np.random.default_rng(season_seed)
        points = {name: 0 for name in self.members}

        # Emparejamientos: una sola vuelta
        for a, b in itertools.combinations(self.members, 2):
            match_seed = int(rng.integers(0, 2**31 - 1))
            # Use self.members to get strategy objects by name
            pa, pb = play_match(self.members[a], self.members[b], rounds=self.league_rounds, seed=match_seed)
            points[a] += pa
            points[b] += pb

        # Sort by points (descending) and name (ascending) for tiebreaker
        self.clasification = sorted(points.items(), key=lambda kv: (-kv[1], kv[0])) #Devuelve list con tuples (name, points)
        self.result = [{"name": n, "points": p, "position": i + 1} for i, (n, p) in enumerate(self.clasification)]
        
    
    def get_top(self):
        """Return dictionary of top strategies by points."""
        k = max(0, int(self.n_ascend_descend))
        return {n: self.members[n] for n, _ in self.clasification[:k]}

    def get_bottom(self):
        """Return dictionary of bottom strategies by points."""
        k = max(0, int(self.n_ascend_descend))
        return {n: self.members[n] for n, _ in (self.clasification[-k:] if k else [])}

    def remove_bottom(self):
        """Remove bottom strategies and update members, strategies, name_to_index."""
        k = max(0, int(self.n_ascend_descend))
        bottom_names = [n for n, _ in (self.clasification[-k:] if k else [])]
        for name in bottom_names:
            self.members.pop(name)
        self.strategies = list(self.members.values())
        self.name_to_index = {name: i for i, name in enumerate(self.members.keys())}
        return self.members

    def remove_top(self):
        """Remove top strategies and update members, strategies, name_to_index."""
        k = max(0, int(self.n_ascend_descend))
        top_names = [n for n, _ in self.clasification[:k]]
        for name in top_names:
            self.members.pop(name)
        self.strategies = list(self.members.values())
        self.name_to_index = {name: i for i, name in enumerate(self.members.keys())}
        return self.members

    def add_members(self, new_members):
        """Add new members and update strategies, name_to_index."""
        self.members.update(new_members)
        self.strategies = list(self.members.values())
        self.name_to_index = {name: i for i, name in enumerate(self.members.keys())}


class League_Tournament:
    def __init__(self, n_seasons, n_leagues, members, rounds,n_per_league, n_ascend_descend):
        self.seasons = n_seasons
        self.n_leagues = n_leagues
        self.members = members  
        self.league_rounds = rounds
        self.n_per_league = n_per_league
        self.n_ascend_descend = n_ascend_descend

        self.leagues = [None] * n_leagues
        self.ascends =  [None] * n_leagues
        self.descends = [None] * n_leagues

    def simulate_first_season(self, seed):
        """
        Simula la primera temporada especial con liga única y reparto por bloques.
        """
        rng = np.random.default_rng(seed)

        # Liga única con todos los miembros
        all_league = League(number=0, members=self.members, rounds=self.league_rounds, n_ascend_descend=0)
        print("\nStart of first season - single league")
        all_league.play(season_seed=seed)

        # Reparto por bloques a ligas
        sorted_global = [row[0] for row in all_league.clasification]  # ya viene en orden desc

        for i in range(self.n_leagues):
            start = i * self.n_per_league
            end = start + self.n_per_league
            block_names = sorted_global[start:end]

            # Crear diccionario parcial {nombre: estrategia}
            block_members = {name: self.members[name] for name in block_names}

            # Crear liga
            league = League(number= i + 1, members=block_members, rounds=self.league_rounds, n_ascend_descend=self.n_ascend_descend)

            self.leagues[i] = league

        # Print results
        for x in range(len(self.leagues)):
            print(f"\nLeague {self.leagues[x].id} Members after first season:")
            for name in self.leagues[x].members.keys():
                print(f"{name}")

    def initialize_spread_leagues(self):
        """
        Divide los miembros en 'n_leagues' ligas con 'n_per_league' participantes cada una.
        Lanza error si no coincide el total.
        """

        if len(self.members) != self.n_leagues * self.n_per_league:
            raise ValueError(f"Error: se esperaban n_leagues * n_per_league = {self.n_leagues * self.n_per_league} estrategias, pero hay {len(self.members)}.")

        # Obtener lista de nombres (orden fijo para reproducibilidad)
        names = list(self.members.keys())

        # Dividir los miembros en bloques de tamaño n_per_league
        for i in range(self.n_leagues):
            start = i * self.n_per_league
            end = start + self.n_per_league
            block_names = names[start:end]

            # Crear diccionario parcial {nombre: estrategia}
            block_members = {name: self.members[name] for name in block_names}

            # Crear liga
            league = League(number= i + 1, members=block_members, rounds=self.league_rounds, n_ascend_descend=self.n_ascend_descend)

            self.leagues[i] = league

        # Print results
        print("\nStart of tournament")
        for x in range(len(self.leagues)):
            print(f"\nLeague {self.leagues[x].id} :")
            for name in self.leagues[x].members.keys():
                print(f"{name}")

    def simulate_seasons(self, seed):
        """
        Simula las temporadas con ascensos/descensos entre ligas.
        """
        rng = np.random.default_rng(seed)

        for season in range(1, self.seasons + 1):
            print(f"\nSeason {season}")

            # Play both leagues
            for league in self.leagues:
                print(f"League {league.id} Members: {[name for name in league.members]}")
                season_seed = int(rng.integers(0, 2**31 - 1))
                league.play(season_seed=season_seed)

            # Determinar ascensos/descensos y eleminarlos de sus ligas
            for x in range(len(self.leagues)):
                #Get top and botttom from leagues
                self.ascends[x] = self.leagues[x].get_top()
                self.descends[x] = self.leagues[x].get_bottom()

                # Remove top and bottom from leagues (except for top of first and bottom of last league)
                if x > 0:
                    self.leagues[x].remove_top()
                if x < self.n_leagues - 1:
                    self.leagues[x].remove_bottom()

            # Exchange participants (except for descends to first and ascends tolast league)
            for x in range(len(self.leagues)):
                if x > 0:
                    self.leagues[x].add_members(self.descends[x-1])
                if x < self.n_leagues - 1:
                    self.leagues[x].add_members(self.ascends[x+1])

            # Print results
            for x in range(len(self.leagues)):
                print(f"\nLeague {self.leagues[x].id} Results:")
                for entry in self.leagues[x].result:
                    print(f"Position {entry['position']}: {entry['name']} ({entry['points']} points)")


tournament = League_Tournament(
    n_seasons=10,
    n_leagues=4,
    members=prueba,
    rounds=100,
    n_per_league=6,
    n_ascend_descend=2,
) 

tournament.simulate_first_season(seed = 40)
tournament.simulate_seasons(seed=42)

"""
# Initialize two leagues with 4 participants each
higher_league_members = {
    name: prueba[name] for name in list(prueba.keys())[:4]
}
lower_league_members = {
    name: prueba[name] for name in list(prueba.keys())[4:8]
}

higher_league = League(number=1, members=higher_league_members, rounds = 100, n_ascend_descend= 2)
lower_league = League(number=2, members=lower_league_members, rounds = 100, n_ascend_descend= 2)

# Simulate 10 seasons
for season in range(1, 11):
    print(f"\nSeason {season}")
    print(f"Higher League Members: {[name for name in higher_league.members]}")
    print(f"Lower League Members: {[name for name in lower_league.members]}")

    # Play both leagues
    higher_league.play(season_seed=season)
    lower_league.play(season_seed=season)

    # Get top 2 from lower league and bottom 2 from higher league
    lower_top = lower_league.get_top()
    higher_bottom = higher_league.get_bottom()

    # Remove participants
    higher_league.remove_bottom()
    lower_league.remove_top()

    # Exchange participants
    higher_league.add_members(lower_top)
    lower_league.add_members(higher_bottom)

    # Print results
    print("\nHigher League Results:")
    for entry in higher_league.result:
        print(f"Position {entry['position']}: {entry['name']} ({entry['points']} points)")
    print("\nLower League Results:")
    for entry in lower_league.result:
        print(f"Position {entry['position']}: {entry['name']} ({entry['points']} points)")

"""

def run_tournament(
    registry = Registry(),
    n_leagues: int = 3,
    rounds: int = 50,
    n_per_league: int = 10,
    n_ascend_descend: int = 2,
    n_seasons: int = 20,
    seed: int = 0,
):
    """
    Torneo con:
      - Temporada 1 especial: liga única con todos; se reparte por bloques a L1..Lk.
      - Temporadas 2..N: cada liga juega; ascensos/descensos simultáneos en intermedias.
    Devuelve:
      {
        "season_tables": [
            {"L0": [...]},                      # T1: tabla global
            {"L1": [...], "L2": [...], ...},    # T2
            ...
        ],
        "leagues_by_season": [
            {"L1": [...], "L2": [...], ...},    # composición tras T1
            {"L1": [...], "L2": [...], ...},    # tras T2
            ...
        ],
    }
    """
    names = list(registry.keys())
    expected = n_leagues * n_per_league
    if len(names) != expected:
        raise ValueError(f"Error: se esperaban n_leagues * n_per_league = {expected} participantes, pero hay {len(names)}.")

    strategies = registry  # alias

    def chunk_into_leagues(sorted_names_desc: list[str]) -> dict:
        """Divide la lista global (ordenada desc por puntos) en L1..Lk por bloques."""
        leagues = {}
        for i in range(n_leagues):
            start = i * n_per_league
            end = start + n_per_league
            leagues[f"L{i+1}"] = sorted_names_desc[start:end]
        return leagues

    season_tables: list[dict] = []
    leagues_by_season: list[dict] = []

    # --- Temporada 1: liga única especial (L0) ---
    t1_seed = seed + 1
    all_league = League("L0", names)
    table_all, _ = all_league.play(strategies, rounds=rounds, season_seed=t1_seed)
    season_tables.append({"L0": table_all})

    # Reparto por bloques: top -> L1, siguientes -> L2, ...
    sorted_global = [row["name"] for row in table_all]  # ya viene en orden desc
    leagues = chunk_into_leagues(sorted_global)
    leagues_by_season.append({k: list(v) for k, v in leagues.items()})

    print("Temporada 1 finalizada.")

    # --- Temporadas normales: 2..n_seasons ---
    for season_idx in range(2, n_seasons + 1):
        base_seed = seed + season_idx
        tables_this_season = {}
        league_tables = {}

        # 1) Jugar cada liga
        for li in range(1, n_leagues + 1):
            lname = f"L{li}"
            league = League(lname, leagues[lname])
            table, _ = league.play(strategies, rounds=rounds, season_seed=base_seed + li)
            league_tables[lname] = table
            tables_this_season[lname] = table

        season_tables.append(tables_this_season)

        # 2) Determinar ascensos/descensos simultáneos
        to_promote = {f"L{i}": [] for i in range(1, n_leagues + 1)}
        to_demote  = {f"L{i}": [] for i in range(1, n_leagues + 1)}

        for li in range(1, n_leagues + 1):
            lname = f"L{li}"
            table = league_tables[lname]

            if li > 1:
                # L2..Lk: suben los primeros n_ascend_descend
                to_promote[lname] = [row["name"] for row in table[:n_ascend_descend]]

            if li < n_leagues:
                # L1..L(k-1): bajan los últimos n_ascend_descend
                to_demote[lname]  = [row["name"] for row in table[-n_ascend_descend:]]

        # 3) Aplicar movimientos
        new_leagues = {k: list(v) for k, v in leagues.items()}

        # quitar de origen
        for li in range(1, n_leagues + 1):
            lname = f"L{li}"
            for n in to_promote[lname]:
                if n in new_leagues[lname]:
                    new_leagues[lname].remove(n)
            for n in to_demote[lname]:
                if n in new_leagues[lname]:
                    new_leagues[lname].remove(n)

        # añadir a destino
        for li in range(1, n_leagues + 1):
            lname = f"L{li}"
            if li > 1:
                dst = f"L{li-1}"  # promociones: Li -> L(i-1)
                new_leagues[dst].extend(to_promote[lname])
            if li < n_leagues:
                dst = f"L{li+1}"  # descensos: Li -> L(i+1)
                new_leagues[dst].extend(to_demote[lname])

        # ordenar por nombre para estabilidad interna (no afecta a puntos)
        for k in new_leagues:
            new_leagues[k] = sorted(new_leagues[k])

        leagues = new_leagues
        leagues_by_season.append({k: list(v) for k, v in leagues.items()})

        print(f"Temporada {season_idx} finalizada.")

    return {
        "season_tables": season_tables,
        "leagues_by_season": leagues_by_season,
    }
