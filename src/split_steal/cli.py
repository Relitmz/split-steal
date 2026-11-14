import typer
from .simulator import run_tournament
from .register import Registry
import pandas as pd

def summarize(csv_path: str):
    df = pd.read_csv(csv_path)
    dfA = df[["A","pa","pb"]].rename(columns={"A":"name","pa":"score","pb":"opp"})
    dfB = df[["B","pb","pa"]].rename(columns={"B":"name","pb":"score","pa":"opp"})
    u   = pd.concat([dfA, dfB], ignore_index=True)

    summary = (u.assign(win=(u["score"] > u["opp"]).astype(int),
                        loss=(u["score"] < u["opp"]).astype(int),
                        tie =(u["score"] == u["opp"]).astype(int))
                 .groupby("name", as_index=False)
                 .agg(matches=("score","size"),
                      wins=("win","sum"),
                      losses=("loss","sum"),
                      ties=("tie","sum"),
                      mean_payoff=("score","mean"),
                      median_payoff=("score","median"))
                 .sort_values(["mean_payoff","wins"], ascending=[False, False]))
    return summary

app = typer.Typer(help="Simulaciones Split/Steal (mínimas)")

@app.command()
def registry():
    return Registry()

@app.command()
def run(n_matches: int = 200,
        rounds: int = 50,
        seed: int = 0,
        noise: float = 0.0,
        out_dir: str = "results"):
    csv_path = run_tournament(n_matches=n_matches, rounds=rounds, seed=seed, noise=noise, out_dir=out_dir)
    typer.echo(f"✅ Resultados guardados en: {csv_path}")

@app.command()
def stats(csv_path: str):
    table = summarize(csv_path)
    typer.echo(table.to_string(index=False))

if __name__ == "__main__":
    app()

