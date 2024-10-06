from pathlib import Path

from run_with_ui import BasicConverter

# change these, then run this file in your IDE
# or alternatively py <this_file.py>
# macOS or Linux users use python3 in place of py

if __name__ == '__main__':
    bc = BasicConverter(
        midi_file=Path("PATH_TO_INPUT_MIDI.mid"),
        output_chart=Path("path_to_output_json.json"),
        event_information=Path("example_event.json"),
        note_types=Path("note_types.txt"),
        bf="bf",
        en="dad",
        gf="gf",
        scroll_speed=2.4,
        song="song_name",
        stage="stage"
    )
    bc.from_midi()
