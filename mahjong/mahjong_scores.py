import json
import pathlib
from logging import exception

import fpdf
import argparse


def compute_stats(j):
    data = {}
    for table in j:
        if "players" not in table:
            print("a round has no player list")
            exit(-1)

        player_scores = []
        for player in table["players"]:
            if player not in data:
                data[player] = {"round": [], "point": 0., "bonus": 0, "vs": {}}

            for player2 in table["players"]:
                if player == player2:
                    continue

                if player2 not in data[player]["vs"]:
                    data[player]["vs"][player2] = [0] * 13  # score, games, win_self, lose_self, win_call, lose_call, plus8, minus8, draw, win_self_hand, win_call_hand, lose_self_hand, lose_call_hand

            player_scores.append([player, 0])

        n = len(player_scores)
        player_scores2 = player_scores + player_scores
        for i, (value, winner, losser) in enumerate(table["games"]):
            i %= n
            if value == 0:
                for player, _ in player_scores2[i: i + 4]:
                    for player2, _ in player_scores2[i: i + 4]:
                        if player is player2:
                            continue

                        data[player]["vs"][player2][1] += 1
                        data[player]["vs"][player2][8] += 1

                continue

            for j, player_score in enumerate(player_scores2[i: i + 4], start=i):
                for player_score2 in player_scores2[i: i + 4]:
                    if player_score is player_score2:
                        continue

                    data[player_score[0]]["vs"][player_score2[0]][1] += 1

                if losser == 0:
                    if j % n != winner - 1:
                        continue

                    player_score[1] += 3 * value + 24
                    for player_score2 in player_scores2[i: i + 4]:
                        if player_score is player_score2:
                            continue

                        data[player_score[0]]["vs"][player_score2[0]][0] += value + 8
                        data[player_score[0]]["vs"][player_score2[0]][2] += 1  # win_self
                        data[player_score[0]]["vs"][player_score2[0]][9] += value

                        player_score2[1] -= value + 8
                        data[player_score2[0]]["vs"][player_score[0]][0] -= value + 8
                        data[player_score2[0]]["vs"][player_score[0]][3] += 1  # lose_self
                        data[player_score2[0]]["vs"][player_score[0]][11] += value
                else:
                    if j % n == winner - 1:
                        continue

                    if j % n == losser - 1:
                        player_scores2[winner - 1][1] += value + 8
                        data[player_scores2[winner - 1][0]]["vs"][player_score[0]][0] += value + 8
                        data[player_scores2[winner - 1][0]]["vs"][player_score[0]][4] += 1  # win_call
                        data[player_scores2[winner - 1][0]]["vs"][player_score[0]][10] += value

                        player_score[1] -= value + 8
                        data[player_score[0]]["vs"][player_scores2[winner - 1][0]][0] -= value + 8
                        data[player_score[0]]["vs"][player_scores2[winner - 1][0]][5] += 1  # lose_call
                        data[player_score[0]]["vs"][player_scores2[winner - 1][0]][12] += value
                    else:
                        player_scores2[winner - 1][1] += 8
                        data[player_scores2[winner - 1][0]]["vs"][player_score[0]][0] += 8
                        data[player_scores2[winner - 1][0]]["vs"][player_score[0]][6] += 1  # plus8

                        player_score[1] -= 8
                        data[player_score[0]]["vs"][player_scores2[winner - 1][0]][0] -= 8
                        data[player_score[0]]["vs"][player_scores2[winner - 1][0]][7] += 1  # minus8

            for player_score in player_scores:
                print(f"{player_score[1]:8}", end="\t")

            print()

        if "bonus" in table:
            for i, bonus in table["bonus"]:
                player_scores[i - 1][1] += bonus
                data[player_scores[i - 1][0]]["bonus"] += bonus

        print()
        print(player_scores)
        print()

        player_scores = sorted(player_scores, key=lambda x: x[1], reverse=True)
        for player, score in player_scores:
            if n == 4 and len(table["games"]) >= 6:
                ranks = [i for i, (_, s) in enumerate(player_scores) if s == score]
                data[player]["round"].append(min(ranks))
                data[player]["point"] += sum(4 >> r for r in ranks) / len(ranks)

    return data


def output_stats(data, path: pathlib.Path):
    stats = []
    for key, value in data.items():
        score, game, win_self, lose_self, win_call, lose_call, plus8, minus8, draw, win_self_hand, win_call_hand, lose_self_hand, lose_call_hand = value["bonus"], 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        pdf = fpdf.FPDF(orientation="landscape", format="A4")
        pdf.add_page()
        pdf.set_font("helvetica", style="B", size=16)
        pdf.cell(text=key + ("'s" if key[-1] != "s" else "'") + f" stats ({path.stem})", align="C", center=True)
        pdf.ln(16)
        pdf.set_font("helvetica", size=11)
        with pdf.table(text_align="CENTER", cell_fill_color=224, cell_fill_mode="ROWS", col_widths=(10,) + (7,) * 13) as table:
            row = table.row()
            for h in ("Name", "Games", "Score", "Win call rate", "Win self rate", "+8 rate", "Lose call rate", "Lose self rate", "-8 rate", "Draw rate", "Average win call hand value", "Average win self hand value", "Average lose call hand value", "Average lose self hand value"):
                row.cell(h)

            for k, (s, g, ws, ls, wc, lc, p8, m8, d, wsh, wch, lsh, lch) in sorted(value["vs"].items(), key=lambda x: (x[1][1], x[1][0], sum(x[1][3:5])), reverse=True):
                score += s
                game += g
                win_self += ws
                lose_self += ls
                win_call += wc
                lose_call += lc
                plus8 += p8
                minus8 += m8
                draw += d
                win_self_hand += wsh
                win_call_hand += wch
                lose_self_hand += lsh
                lose_call_hand += lch

                if g <= 0:
                    continue

                row = table.row()
                row.cell(k)
                row.cell(str(g))
                row.cell(str(s))
                row.cell(f"{100 * wc / g:.2f}")
                row.cell(f"{100 * ws / g:.2f}")
                row.cell(f"{100 * p8 / g:.2f}")
                row.cell(f"{100 * lc / g:.2f}")
                row.cell(f"{100 * ls / g:.2f}")
                row.cell(f"{100 * m8 / g:.2f}")
                row.cell(f"{100 * d / g:.2f}")
                row.cell(f"{(wch / wc) if wc > 0 else 0:.2f}")
                row.cell(f"{(wsh / ws) if ws > 0 else 0:.2f}")
                row.cell(f"{(lch / lc) if lc > 0 else 0:.2f}")
                row.cell(f"{(lsh / ls) if ls > 0 else 0:.2f}")

        pdf.output(path / f"{key.replace(" ", "_")}_{path.stem}.pdf")

        if game <= 0:
            continue

        most_taken = sorted(((value["vs"][k][0], k) for k in value["vs"] if value["vs"][k][0] > 0), reverse=True)
        most_taken = "\n".join(map(lambda x: f"{x[1]} ({x[0]})", most_taken[:3]))
        most_given = sorted((value["vs"][k][0], k) for k in value["vs"] if value["vs"][k][0] < 0)
        most_given = "\n".join(map(lambda x: f"{x[1]} ({x[0]})", most_given[:3]))
        most_played = sorted(((value["vs"][k][1], k) for k in value["vs"] if value["vs"][k][1] > 0), reverse=True)
        most_played = "\n".join(map(lambda x: f"{x[1]} ({x[0]})", most_played[:3]))
        if game / 3 != game // 3:
            print(key, "warning game isn't divisible by 3")

        game //= 3
        if win_self / 3 != win_self // 3:
            print(key, "warning win_self isn't divisible by 3 ->", win_self)

        win_self //= 3
        if 2 * win_call != plus8:
            print(key, "warning 2 * win_call != plus8 ->", win_call, plus8)

        if draw / 3 != draw // 3:
            print(key, "warning draw isn't divisible by 3 ->", draw)

        draw //= 3
        if win_self_hand / 3 != win_self_hand // 3:
            print(key, "warning win_self_hand isn't divisible by 3")

        win_self_hand //= 3
        win_call_rate = f"{100 * win_call / game:.2f}"
        win_self_rate = f"{100 * win_self / game:.2f}"
        lose_call_rate = f"{100 * lose_call / game:.2f}"
        lose_self_rate = f"{100 * lose_self / game:.2f}"
        minus8_rate = f"{100 * minus8 / game:.2f}"
        draw_rate = f"{100 * draw / game:.2f}"
        avg_win_call_hand = f"{(win_call_hand / win_call) if win_call > 0 else 0:.2f}"
        avg_win_self_hand = f"{(win_self_hand / win_self) if win_self > 0 else 0:.2f}"
        avg_lose_call_hand = f"{(lose_call_hand / lose_call) if lose_call > 0 else 0:.2f}"
        avg_lose_self_hand = f"{(lose_self_hand / lose_self) if lose_self > 0 else 0:.2f}"
        #avg_rank = f"{(sum(value["round"]) / len(value["round"]) + 1) if value["round"] else 0:.3f}"
        avg_points = f"{(value["point"] / len(value["round"])) if value["round"] else 0:.3f}"
        ranks = [0] * 4
        if value["round"]:
            for r in value["round"]:
                ranks[r] += 100

            for i in range(len(ranks)):
                ranks[i] = f"{ranks[i] / len(value["round"]):0.2f}"

        stats.append((key, score, game, len(value['round']), avg_points, *ranks, win_call_rate, win_self_rate, lose_call_rate, lose_self_rate, minus8_rate, draw_rate, avg_win_call_hand, avg_win_self_hand, avg_lose_call_hand, avg_lose_self_hand, most_taken, most_given, most_played))

    stats.sort(key=lambda x: (-x[1], x[2], x[0]))
    pdf = fpdf.FPDF(orientation="portrait", format="A4")
    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(text=f"General stats ({path.stem})", align="C", center=True)
    pdf.ln(16)
    pdf.set_font("helvetica", size=11)
    with pdf.table(text_align="CENTER", cell_fill_color=224, cell_fill_mode="ROWS", col_widths=(20, 12, 12, 12, 12, 8, 8, 8, 8)) as table:
        row = table.row()
        for h in ("Name", "Score", "Games", "Valid rounds\n(4P6G+)", "Average points", "1st rank rate", "2nd rank rate", "3rd rank rate", "4th rank rate"):
            row.cell(h)

        for stat in stats:
            row = table.row()
            row.cell(stat[0])
            for e in stat[1:9]:
                row.cell(str(e))

    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(text="Outcome stats", align="C", center=True)
    pdf.ln(16)
    pdf.set_font("helvetica", size=11)
    with pdf.table(text_align="CENTER", cell_fill_color=224, cell_fill_mode="ROWS", col_widths=(16, 14, 14, 14, 14, 14, 14)) as table:
        row = table.row()
        for h in ("Name", "Win call rate", "Win self rate", "Lose call rate", "Lose self rate", "-8 rate", "Draw rate"):
            row.cell(h)

        for stat in stats:
            row = table.row()
            row.cell(stat[0])
            for e in stat[9:15]:
                row.cell(str(e))

    pdf.add_page()
    pdf.set_font("helvetica", style="B", size=16)
    pdf.cell(text="Other stats", align="C", center=True)
    pdf.ln(16)
    pdf.set_font("helvetica", size=11)
    with pdf.table(text_align="CENTER", cell_fill_color=224, cell_fill_mode="ROWS", col_widths=(14, 7, 7, 7, 7, 19, 20, 19)) as table:
        row = table.row()
        for h in ("Name", "Avg win call hand value", "Avg win self hand value", "Avg lose call hand value", "Avg lose self hand value", "Top3\nmost taken", "Top3\nmost given", "Top3\nmost played"):
            row.cell(h)

        for stat in stats:
            row = table.row()
            row.cell(stat[0])
            for e in stat[15:22]:
                row.cell(str(e))

    pdf.output(path / f"ranking_{path.stem}.pdf")


def merge_stats(dst, src):
    for player in src:
        if player not in dst:
            dst[player] = src[player]
            continue

        dst[player]["round"].extend(src[player]["round"])
        dst[player]["point"] += src[player]["point"]
        dst[player]["bonus"] += src[player]["bonus"]
        for player2 in src[player]["vs"]:
            if player2 not in dst[player]["vs"]:
                dst[player]["vs"][player2] = src[player]["vs"][player2]
                continue

            for i in range(len(src[player]["vs"][player2])):
                dst[player]["vs"][player2][i] += src[player]["vs"][player2][i]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", metavar="PATH", type=pathlib.Path, default=".", help="a file or directory path (do all .json + global), default=\".\"")
    parser.add_argument("-o", metavar="PATH", type=pathlib.Path, default=".", help="output root path (create if it doesn't exist), default=\".\"")
    args = parser.parse_args()
    if not args.i.exists():
        parser.print_help()
        exit(-1)

    try:
        args.o.mkdir(parents=True, exist_ok=True)
    except FileNotFoundError as e:
        print(e)
        exit(-2)

    if args.i.is_dir():
        global_stats = {}
        for f in pathlib.Path(args.i).glob("*.json"):
            stats = compute_stats(json.load(open(f, encoding="UTF8")))
            p = args.o / f.stem
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)

            output_stats(stats, p)
            merge_stats(global_stats, stats)

        p = args.o / "global"
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)

        output_stats(global_stats, p)
    elif args.i.is_file():
        p = args.o / args.i.stem
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)

        output_stats(compute_stats(json.load(open(args.i, encoding="UTF8"))), p)
    else:
        parser.print_help()
        exit(-1)


