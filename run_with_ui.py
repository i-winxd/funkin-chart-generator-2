import json
import math
import re
import sys
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import Optional, cast, TypedDict, Union

import mido

from chart_gen import MidiConv, RegularFNFNoteListener, FNFMetadata, AbstractEventListener, AbstractFNFEvent, \
    FNFEvent, ExtraData, AbstractFNFNote, FNFNote, get_actual_duration
from midi_processing import midi_to_representation, Note
from ui import DataclassUI


class CustomEventMetadata(TypedDict):
    track_name: str
    event_name: str
    v1: Union[str, int, bool, float]  # value for v1.
    v2: Union[str, int, bool, float]  # value for v2.


@dataclass
class CustomEventListener(AbstractEventListener):
    event_metadata: CustomEventMetadata

    def process_event(self, note: Note, time_ms: float, extra: ExtraData) -> Optional[AbstractFNFEvent]:

        def interpret_v_script(scr: str, pitch_: int, channel_: int) -> str:
            R"""When specifying a value for v1 or v2, you may put in an expression that
            can depend on either PITCH or CHANNEL. beware, channels count from 0.

            A proper expression is any string put in v1 or v2 that matches this syntax:
            [PITCH or CHANNEL][*<ANY NUMBER>][(+ or -)<ANY NUMBER>],
            Where the multiplication and additive operations are optional. PITCH and CHANNEL
            must be in all caps, and you cannot use both.

            Examples:

            - 'PITCH-60'
            - 'CHANNEL+1' (this matches FL Studio's channel numbering, counting from 1)
            - 'PITCH*2-60'
            - 'PITCH/6+4

            The multiplicative operation must be applied first before the additive operation.
            If you really wanted to do the opposite, such as (PITCH+a)*b, then
            you'll have to write `PITCH*b+(ab)` where `(ab) == a * b`, which you have to
            evaluate yourself since expressions more complex than that are not allowed.

            If what you wrote did not match this syntax, then by default it will
            just return `scr`.


            And your actual expression in the test string.
            If it matches, then you have a valid expression.


            The expression is evaluated using your regular order of operations. Why
            did I create an entire parser here

            """

            def process_expr(numeric_input: int, searched_inner: re.Match[str]) -> str:
                multiplicative = searched_inner.group(1)[1:]
                if multiplicative == '':
                    multiplicative = 1
                exponent = (1 if searched_inner.group(1)[0] == "*" else -1) if searched_inner.group(1) else 1
                additive = searched_inner.group(2)[1:]
                if additive == '':
                    additive = 0
                multiplier = (1 if searched_inner.group(2)[0] == "+" else -1) if searched_inner.group(2) else 1
                numeric_opt = numeric_input * (float(multiplicative) ** exponent) + (additive * multiplier)
                if math.isclose(numeric_opt, round(numeric_opt)):
                    numeric_opt = round(numeric_opt)
                else:
                    numeric_opt = round(numeric_opt, 3)
                ops_s_inner = str(numeric_opt)
                return ops_s_inner

            pitch_reg = re.compile(r"^PITCH([*/]-?\d+(?:\.\d+)?)?([+-]\d+(?:\.\d+)?)?$")
            searched = pitch_reg.search(scr)
            if searched is not None:
                op_s = process_expr(pitch_, searched)
                return op_s
            channel_reg = re.compile(r"^CHANNEL([*/]-?\d+(?:\.\d+)?)?([+-]\d+(?:\.\d+)?)?$")
            channel_searched = channel_reg.search(scr)
            if channel_searched is not None:
                op_s = process_expr(channel_, channel_searched)
                return op_s
            return scr

        pitch = note.pitch
        channel = note.channel

        value_1 = interpret_v_script(str(self.event_metadata["v1"]), pitch, channel)
        value_2 = interpret_v_script(str(self.event_metadata["v2"]), pitch, channel)

        return FNFEvent(time_ms, self.event_metadata["event_name"], value_1, value_2)


@dataclass
class BasicConverter(DataclassUI):
    midi_file: Path = field(
        metadata={
            'filetypes': [('MIDI files', '*.mid')]
        })
    output_chart: Path = field(
        metadata={
            'filetypes': [('JSON files', '*.json')],
            'save': True
        })
    event_information: Path = field(default=Path(""),
                                    metadata={
                                        'filetypes': [('JSON files', '*.json')],
                                    })
    note_types: Path = field(default=Path(""),
                             metadata={
                                 'filetypes': [('txt files', '*.txt')]
                             })
    bf: str = "bf"
    en: str = "dad"
    gf: str = "gf"
    scroll_speed: float = 2.4
    song: str = ""
    stage: str = "stage"

    def from_midi(self) -> None:

        if self.event_information.is_dir() or (not self.event_information.exists()):
            print("No events! This is fine, just acting like there are no events.")
            evs = []
        else:
            with open(self.event_information, "r", encoding="UTF-8") as jsf:
                evs: list[CustomEventMetadata] = json.load(jsf)
                if not isinstance(evs, list):
                    raise ValueError(
                        "Event information must be in a list. "
                        "Did you forget to wrap it around with [ square brackets ]?")
        ev_listeners = [
            CustomEventListener(
                track=sev["track_name"],
                event_metadata=sev
            ) for sev in evs
        ]

        if self.note_types.is_dir() or (not self.note_types.exists()):
            print("No note types! This is fine")
            note_types = []
        else:
            with open(self.note_types, "r", encoding="UTF-8") as ntf:
                note_types_str = ntf.read()
                note_types = [c.split("//")[0].strip() for c in note_types_str.split("\n")]

        if self.song == "":
            self.song = self.output_chart.parts[-1].split(".")[0]

        midi_file = mido.MidiFile(self.midi_file.__str__())
        midi_representation = midi_to_representation(midi_file)
        midi_conv = MidiConv(
            note_listeners=[
                ModifiedFNFNoteListener(
                    track="en",
                    char=0,
                    note_types=note_types
                ),
                ModifiedFNFNoteListener(
                    track="bf",
                    char=1,
                    note_types=note_types
                )
            ],
            event_listeners=ev_listeners,
            cam_track="cam"
        )
        c_json = midi_conv.process_midi(midi_representation,
                                        FNFMetadata(
                                            bf=self.bf,
                                            en=self.en,
                                            gf=self.gf,
                                            scroll_speed=self.scroll_speed,
                                            song=self.song,
                                            stage=self.stage
                                        ))
        with open(self.output_chart.__str__(), "w", encoding="UTF-8") as f:
            json.dump(c_json, f)


@dataclass
class ModifiedFNFNoteListener(RegularFNFNoteListener):
    """Listener for a regular FNF note.
    """
    note_types: list[str]

    def process_note(self, note: Note, time_ms: float, bpm: float, extra: ExtraData) -> Optional[AbstractFNFNote]:
        if note.pitch - 60 in range(0, 4):
            raw_note_duration = get_actual_duration(note.beat, note.duration, extra.bpm_changes) * 1000
            # I LOVE RELU
            raw_note_duration = max(0.0, raw_note_duration - 100.0)
            if raw_note_duration < 350.0 and note.velocity >= 50:
                raw_note_duration = 0

            channel = note.channel
            descriptor = (self.note_types[channel] if len(self.note_types) > channel else '').strip()
            if descriptor:
                return FNFNote(char=self.char, time=time_ms, arrow=note.pitch - 60, hold=raw_note_duration,
                               arrow_count=4, extra=descriptor)
            else:
                return FNFNote(char=self.char, time=time_ms, arrow=note.pitch - 60, hold=raw_note_duration,
                               arrow_count=4)
        else:
            return None


def _validate_basic_converter(bcc: BasicConverter) -> Optional[str]:
    if bcc.song == "":
        return "You must specify a song"
    if bcc.midi_file.__str__() == ".":
        return "You must specify the path to the MIDI file"
    if bcc.output_chart.__str__() == ".":
        return "You must specify the path to save the chart"
    if bcc.output_chart.suffix != ".json":
        return "output chart must end with .json"

    if bcc.event_information.exists() and not bcc.event_information.is_dir():
        if bcc.event_information.suffix != ".json":
            return "Event information must be a .json file"
        try:
            with open(bcc.event_information, "r", encoding="UTF-8") as evf:
                json_stuff = json.load(evf)
            if not isinstance(json_stuff, list):
                return "Your event JSON is not a list. Make sure it's wrapped in [ square brackets ]"
            else:
                for i, ts in enumerate(json_stuff):
                    tst = cast(CustomEventMetadata, ts)
                    keys_set = set(tst.keys())
                    json_key_diff = ({"track_name", "event_name", "v1", "v2", }).difference(keys_set)
                    if json_key_diff.__len__() != 0:
                        return f"Index {i} of your event JSON are missing these keys: {json_key_diff}"
        except JSONDecodeError:
            return "We checked your event info JSON and it isn't a valid JSON. GET RID OF YOUR COMMENTS"

    return None


if __name__ == '__main__':
    bc = cast(BasicConverter,
              BasicConverter.get_instance_from_ui("FnF MIDI to chart", "Check the readme for more information",
                                                  custom_check=_validate_basic_converter))

    try:
        bc.from_midi()
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        input("Something went wrong, so the error is displayed here. Input to close program")
    except KeyError as e:
        print(f"{e}", file=sys.stderr)
        input("Something went wrong, so the error is displayed here. Input to close program")
