from pathlib import Path

from run_with_ui import BasicConverter
import argparse

# change these, then run this file in your IDE
# or alternatively py <this_file.py>
# macOS or Linux users use python3 in place of py

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("midi", help="Path to input MIDI file (.mid, rb)")
    parser.add_argument("output", help="Path to output chart (.json, w), do NOT add difficulty suffix")
    parser.add_argument("-v", "--event_info", help="Path to event info file (.json, r)", default=".")
    parser.add_argument("-n", "--note_types", help="Path to note types file (.txt, r)", default=".")
    parser.add_argument("-b", "--bf", help="Name of BF", default="bf")
    parser.add_argument("-e", "--en", help="Name of enemy character (left)", default="dad")
    parser.add_argument("-g", "--gf", help="Name of GF", default="gf")
    parser.add_argument("-s", "--scroll", type=float, help="Scroll speed", default=2.4)
    parser.add_argument("-m", "--song", help="Name of song. If omitted, will be based on output json file name",
                        default="")
    parser.add_argument('-l', '--stage', help="Stage", default="Stage")
    args = parser.parse_args()
    bc = BasicConverter(
        midi_file=Path(args.midi),
        output_chart=Path(args.output),
        event_information=Path(args.event_info),
        note_types=Path(args.note_types),
        bf=args.bf,
        en=args.en,
        gf=args.gf,
        scroll_speed=float(args.scroll),
        song=args.song,
        stage=args.stage
    )
    bc.from_midi()
