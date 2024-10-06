import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Union, Optional, final, cast

from midi_processing import Note, MidiRepresentation, TempoChange, TimeSignature

VAL = Union[int, float, str]
INT_OR_BOOL = Union[int, bool]
DEFAULT_BPM = 120


def get_actual_duration(beat: float, duration_beats: float, tcs: list[TempoChange]) -> float:
    """Return how long this note actually is, in seconds"""
    end_dur = beat + duration_beats
    final_point = beat_to_s(end_dur, tcs)
    return final_point - beat_to_s(beat, tcs)


def beat_to_s(beat: float, tcs: list[TempoChange]) -> float:
    tcs = sorted(tcs, key=lambda s: s.beat)
    bpm = 120  # current bpm
    cur_time = 0.0  # time since the last tempo change
    last_tc = 0.0  # beat of the last tempo change

    # 120 -> 120 @ 0, cur_time = 0
    # 120 -> 240 @ 1, cur_time = 0.5, last_tc = 1, bpm = 120
    # @ 3, 0.5 + 0.25 * (2) = 0.5 + 0.5 = 1
    for tc in tcs:
        if tc.beat < beat:
            last_tc = tc.beat
            cur_time += (60 / bpm) * (tc.beat - last_tc)
            bpm = tc.new_bpm
        else:
            break
    return cur_time + (60 / bpm) * (beat - last_tc)


def ntn(note_name: str) -> int:
    """Convert note in text to note number
    e.g. C5 -> 60
    Not case-sensitive."""
    n_re = re.compile(r"^([A-G])([#B]?)(\d{1,2})$")
    searched = n_re.search(note_name.strip().upper())
    if searched is None:
        raise ValueError("Not a valid note!")
    base = searched.group(1)
    base_dict = {
        "C": 0,
        "D": 2,
        "E": 4,
        "F": 5,
        "G": 7,
        "A": 9,
        "B": 11
    }
    sharp_flat = searched.group(2)
    sf_d = {
        "#": 1,
        "B": -1,
        "": 0
    }
    octave = int(searched.group(3))
    return octave * 12 + base_dict[base] + sf_d[sharp_flat]


@dataclass
class AbstractFNFNote(ABC):
    """This class represents a note,
    that would represent an arrow in the FNF chart."""
    time: float

    @abstractmethod
    def export_note(self, must_hit: bool) -> list[Any]:
        """Export the note into the chart.
        This would be put into one element in
        a ``sectionNotes`` list."""
        pass


@dataclass
class ExtraData:
    """Additional data to pass in all variants of ``process_note``, if needed."""
    note_index: int
    notes: list[Note]
    bpm_changes: list[TempoChange]


@dataclass
class FNFNote(AbstractFNFNote):
    char: int  # the character the note belongs to, starting from 0.
    # by default, 0=en, 1=bf. If your mod has over 2 characters
    # then you need to know how your chart format organizes it
    # for you

    arrow: int  # ALWAYS FROM 0. EXPORT AUTOCORRECTS FOR MUST HITS
    # SO BY DEFAULT 0=LEFT, 1=DOWN, 2=UP, 3=RIGHT REGARDLESS OF
    # WHO SINGS THIS
    # if your song has over 4 keys, then the range is from 0 to (key count - 1)
    # and you will have to modify ``arrow_count``
    hold: float  # non-negative, in ms
    # extra is
    extra: Optional[VAL] = None  # int, float, str; can be anything
    arrow_count: int = 4

    # though this is usually the name of the alt note
    # This is almost always a string and is the name
    # attached to the note

    def export_note(self, must_hit: INT_OR_BOOL) -> list[Any]:
        pad_up = int(bool((not bool(must_hit) and self.char == 1) or (bool(must_hit) and self.char == 0)))

        arrow = self.arrow + self.arrow_count * pad_up

        if self.extra is None:
            return [
                self.time, arrow, self.hold
            ]
        else:
            return [
                self.time, arrow, self.hold, self.extra
            ]


@dataclass
class AbstractFNFEvent(ABC):
    """AN EVENT USUALLY CONSISTS OF
    [EVENT NAME, V1, V2]
    """
    time: float  # when the event occurs since start of song in ms

    def export_event(self) -> list[list[Any]]:
        """Export the information associated with an event.
        Do not export the time.
        The reason why the event is in a 2D list, is
        because there can be multiple events that
        occur at the same time.
        """
        pass

    @final
    def export_event_with_time(self) -> list[Any]:
        """Export the event with the time attached to it,
        which will typically belong in the ``events`` array
        in a chart's event.

        Export format: ``tuple[float, list[list[Any]]]``

        DO NOT OVERRIDE THIS METHOD, THIS METHOD IS FINAL
        """
        return [self.time, self.export_event()]


@dataclass
class FNFEvent(AbstractFNFEvent):
    name: str
    v1: str
    v2: str

    def export_event(self) -> list[list[Any]]:
        return [[self.name, self.v1, self.v2]]


@dataclass
class AbstractEventListener(ABC):
    track: str  # only consider notes in this track

    @abstractmethod
    def process_event(self, note: Note, time_ms: float, extra: ExtraData) -> Optional[AbstractFNFEvent]:
        """Process an event. Return the event if you want it added.

        You can have the event depend on ``Note``. When returning
        the event, **ALWAYS** pass in the ``time_ms`` from the
        arguments there into the time of the event, which all
        event classes should have.

        Example implementation:

        ```
        action = ["among", "us", "is", "in", "real", "life"]
        return FNFEvent("Glungus", action[note.pitch - 60], str(note.channel))
        ```

        Remember, you can use ``self.track`` if you really need the
        track name.
        """
        pass


@dataclass
class AbstractNoteListener(ABC):
    """Per abstract note listener,
    this outputs a note based on a note."""

    track: str  # only consider notes in this track.

    # if you want to consider multiple tracks maybe
    # duplicate instances of this class with this
    # variable modified.

    @abstractmethod
    def process_note(self, note: Note, time_ms: float, bpm: float, extra: ExtraData) -> Optional[AbstractFNFNote]:
        """Method is called per note that is in any of the tracks
        in ``self.track``. You may either return an FNF note that
        gets added to the chart, or return None if you do not want
        that note to be processed.

        We put `time_ms` in the argument since MIDI Processor notes
        do not carry BPM change information, and FNF uses time
        since song start.

        `bpm` is the current BPM of when the note is
        being played. Behavior can get
        a bit weird if a sustain note goes over
        a BPM change section.
        """
        pass


@dataclass
class RegularFNFNoteListener(AbstractNoteListener):
    """Listener for a regular FNF note.
    """
    char: int  # the character of whom this note may belong to

    # 0=en, 1=bf by default. This is an int instead of a bool
    # due to certain mods having more than 2 characters.

    def process_note(self, note: Note, time_ms: float, bpm: float, extra: ExtraData) -> Optional[AbstractFNFNote]:
        if note.pitch - 60 in range(0, 4):
            raw_note_duration = get_actual_duration(note.beat, note.duration, extra.bpm_changes) * 1000
            # I LOVE RELU
            raw_note_duration = max(0.0, raw_note_duration - 100.0)
            if raw_note_duration < 350.0 and note.velocity >= 50:
                raw_note_duration = 0
            return FNFNote(char=self.char, time=time_ms, arrow=note.pitch - 60, hold=raw_note_duration,
                           arrow_count=4)
        else:
            return None


def get_bpm_so_far(beat: float, tempo_changes: list[TempoChange]) -> float:
    if not tempo_changes:
        return DEFAULT_BPM

    tc_sorted = sorted(tempo_changes, key=lambda s: s.beat)
    for i, tc in enumerate(tempo_changes):
        if beat >= tc.beat:
            return tc_sorted[i].new_bpm_rounded
    return tc_sorted[-1].new_bpm_rounded


@dataclass
class MidiConvOpt:
    fnf_notes: list[AbstractFNFNote]
    events: list[AbstractFNFEvent]


@dataclass
class RawSection:
    bf_cam: bool
    notes: list[AbstractFNFNote]
    gf_section: bool
    alt_anim: bool
    section_beats: float
    new_bpm: Optional[float]


def find_index_first_above(sorted_list: list[float], value: float, b: int = 0, e: Optional[int] = None) -> int:
    """Find the first index i such that sorted_list[i] <= value + epsilon
    Return -1 if no such index exists

    Only search for values between b:e
    """
    eps = 0.0000001

    if e is None:
        e = len(sorted_list)

    if e - b == 0:
        return -1
    elif e - b == 1:
        return b if sorted_list[b] <= value + eps else -1

    m = (b + e) // 2

    if sorted_list[m] <= value + eps:
        rv = find_index_first_above(sorted_list, value, m, e)
    else:
        rv = find_index_first_above(sorted_list, value, b, m)
    return rv


def flagged_sections(target_track: str, midi_rep: MidiRepresentation, sections_generated: list[float]) -> list[bool]:
    """Return a list the same length of sections_generated, with indices true if there exists
    a note in cam_track that is C# or higher in that section, for each section.

    :param target_track: the track to target
    :param midi_rep:
    :param sections_generated:
    :return: List of False if target_track is not a track
    """
    target_track_2 = next((v for v in midi_rep.tracks.values() if v.track_name == target_track), None)
    if target_track_2 is None:
        camera_pointing_to_bf: list[bool] = [False for _ in sections_generated]
    else:
        camera_pointing_to_bf: list[bool] = []
        target_track_notes = sorted(target_track_2.notes, key=lambda n: n.beat)
        target_track_beats = [n.beat for n in target_track_notes]
        previous_choice = False
        for sg in sections_generated:
            # sg is the time the section starts.
            # I want to find the first note that
            # starts during that section
            tg_beat = find_index_first_above(target_track_beats, sg - 0.001)

            # couldn't find any note marker, take the previous choice
            if tg_beat == -1 or (tg_beat + 1 < len(target_track_beats) and (
                    target_track_notes[tg_beat].beat >= target_track_beats[tg_beat + 1] - 0.001)):
                camera_pointing_to_bf.append(
                    previous_choice
                )
            else:
                # could find a note marker, so I am taking the previous choice
                found_track = target_track_notes[tg_beat]
                new_choice = bool(found_track.note >= 61)
                camera_pointing_to_bf.append(
                    new_choice
                )
                previous_choice = new_choice
    return camera_pointing_to_bf


def get_json_notes_list(initial_bpm: float, ses_col: list[RawSection]) -> list[dict[str, Any]]:
    """Return the notes that would be injected into the JSON file"""
    json_notes_list = []
    current_bpm = initial_bpm
    for ses in ses_col:
        sd = {
            "sectionBeats": ses.section_beats,
            "altAnim": ses.alt_anim,
            "mustHitSection": ses.bf_cam,
            "lengthInSteps": 16,
            "typeOfSection": 0,
            "sectionNotes": [sn.export_note(ses.bf_cam) for sn in ses.notes],
            "gfSection": ses.gf_section,
            "bpm": current_bpm,
            "changeBPM": False
        }
        if ses.new_bpm is not None:
            sd["bpm"] = ses.new_bpm
            sd["changeBPM"] = True
            current_bpm = ses.new_bpm
        json_notes_list.append(sd)
    return json_notes_list


@dataclass
class FNFMetadata:
    en: str  # name of the enemy
    bf: str  # name of the playable character
    gf: str  # gfVersion
    song: str  # name of the song
    stage: str
    scroll_speed: float
    needs_voices: bool = True
    valid_score: bool = True
    splash_skin: Optional[str] = None


@dataclass
class MidiConv:
    note_listeners: list[AbstractNoteListener]
    """All associated note listeners"""

    event_listeners: list[AbstractEventListener]
    cam_track: str = "cam"
    gf_track: str = "gf"
    alt_anim: str = "alt"

    def process_midi(self, midi_rep: MidiRepresentation, metadata: FNFMetadata) -> dict[str, Any]:

        initial_bpm = midi_rep.bpm_changes[0].new_bpm_rounded if midi_rep.bpm_changes else 120

        song_length = max(
            math.ceil(max(max(n.beat + n.duration for n in v.notes) for v in midi_rep.tracks.values()) + 1),
            math.ceil(max(bc.beat + 14 for bc in midi_rep.bpm_changes)),
            math.ceil(max(tcc.beat + 14 for tcc in midi_rep.time_signature_changes)))
        fnf_notes = self._get_fnf_notes(midi_rep)
        event_notes = self._get_event_notes(midi_rep)

        # SECTIONS EXPORT GENERATOR
        raw_section_collection = self._generate_section_collection(fnf_notes, midi_rep, song_length)

        json_notes_list = get_json_notes_list(initial_bpm, raw_section_collection)
        json_events = [ev.export_event_with_time() for ev in event_notes]

        song_data = {
            "player1": metadata.bf,
            "events": json_events,
            "player2": metadata.en,
            "gfVersion": metadata.gf,
            "song": metadata.song,
            "stage": metadata.stage,
            "needsVoices": metadata.needs_voices,
            "validScore": metadata.valid_score,
            "bpm": initial_bpm,
            "speed": metadata.scroll_speed,
            "notes": json_notes_list,
            "generatedBy": "chart-gen-10-5"
        }
        if metadata.splash_skin:
            song_data["splashSkin"] = metadata.splash_skin

        json_data = {
            "song": song_data
        }
        return json_data

    @final
    def _get_event_notes(self, midi_rep: MidiRepresentation) -> list[AbstractFNFEvent]:
        event_notes: list[AbstractFNFEvent] = []
        for event_listener in self.event_listeners:
            target_track = next((x for x in midi_rep.tracks.values() if x.track_name == event_listener.track), None)
            if target_track is None:
                continue
            for i, note in enumerate(target_track.notes):
                ev_n = (event_listener.process_event(note, 1000 * beat_to_s(note.beat, midi_rep.bpm_changes),
                                                     ExtraData(i, target_track.notes, midi_rep.bpm_changes)))
                if ev_n is not None:
                    event_notes.append(ev_n)
        return event_notes

    @final
    def _get_fnf_notes(self, midi_rep: MidiRepresentation) -> list[AbstractFNFNote]:
        fnf_notes: list[AbstractFNFNote] = []
        for listener in self.note_listeners:
            target_track = next((x for x in midi_rep.tracks.values() if x.track_name == listener.track), None)
            if target_track is None:
                continue
            for i, note in enumerate(target_track.notes):
                tpn = listener.process_note(note,
                                            1000 * beat_to_s(note.beat, midi_rep.bpm_changes),
                                            get_bpm_so_far(note.beat,
                                                           midi_rep.bpm_changes),
                                            ExtraData(i, target_track.notes, midi_rep.bpm_changes))
                if tpn is not None:
                    tpn_nn = tpn
                    fnf_notes.append(tpn_nn)
        return fnf_notes

    @final
    def _generate_section_collection(self, fnf_notes: list[AbstractFNFNote], midi_rep: MidiRepresentation,
                                     song_length: int) -> list[RawSection]:
        sections_generated, section_numerator = generate_sections(midi_rep, song_length)
        camera_pointing_to_bf = flagged_sections(self.cam_track, midi_rep, sections_generated)
        gf_section = flagged_sections(self.gf_track, midi_rep, sections_generated)
        alt_anim_sections = flagged_sections(self.alt_anim, midi_rep, sections_generated)
        integrated_tempo_changes = integrate_tempo_changes(
            sections_generated, midi_rep.bpm_changes
        )
        sections = sorted([beat_to_s(s, midi_rep.bpm_changes) * 1000 for s in
                           sections_generated])  # ensure sections is always sorted
        ses_col = [RawSection(bf_cam=camera_pointing_to_bf[i], notes=[], gf_section=gf_section[i],
                              alt_anim=alt_anim_sections[i],
                              section_beats=section_numerator[i],
                              new_bpm=integrated_tempo_changes[i]
                              ) for i in
                   range(len(sections_generated))]
        for note in fnf_notes:
            ses_idx = find_index_first_above(sections, note.time)
            ses_col[ses_idx].notes.append(note)
        return ses_col


def generate_sections(midi_rep: MidiRepresentation, song_length: int) -> tuple[list[float], list[float]]:
    """Song length is the upper bound for how long the song is, in beats (with more nudges added).
    Return the beat markers for when a new section should be created.

    The first list returned is always sorted
    The second list represents the section's beats

    This really should NOT be returning two values
    """
    tc_changes = midi_rep.time_signature_changes
    if not tc_changes:
        tc_changes = [TimeSignature(4, 4, 0)]
    current_tc: int = 0
    current_beat: float = 0.0

    beat_markers: list[float] = [0]
    section_beats: list[float] = [4]

    while current_beat <= song_length:
        next_candidate_1 = current_beat + tc_changes[current_tc].numerator
        next_candidate_2 = math.inf
        target_tc = tc_changes[current_tc]
        if (current_tc + 1) in range(0, len(tc_changes)):
            next_candidate_2 = tc_changes[current_tc + 1].beat

        next_beat = min(next_candidate_1, next_candidate_2)
        if next_candidate_2 <= next_candidate_1:
            target_tc = tc_changes[current_tc + 1]
            current_tc += 1
            section_beats[-1] = next_beat - current_beat

        beat_markers.append(next_beat)
        section_beats.append(target_tc.numerator)

        current_beat = next_beat

    return beat_markers, section_beats


def integrate_tempo_changes(section_beat_markers: list[float], tempo_changes: list[TempoChange]) -> list[
    Optional[float]
]:
    """If there are tempo changes at the
    start of each section integrate them

    Return a list of tempo changes for each
    section, or None if there is no
    tempo change

    An exception will be raised if there are leftover
    unaccounted for tempo changes.
    """
    tc_indices: set[int] = set()
    tc_stuff: list[Optional[float]] = []
    for sbm in section_beat_markers:
        tc_found = next(((i, tc) for i, tc in enumerate(tempo_changes) if math.isclose(tc.beat, sbm)), (-1, None))
        tc_idx = tc_found[0]
        tc_inst = tc_found[1]
        if tc_inst is not None:
            assert tc_idx != -1
            tc_inst_v = cast(TempoChange, tc_inst)
            tc_stuff.append(tc_inst_v.new_bpm_rounded)
            tc_indices.add(tc_idx)
        else:
            tc_stuff.append(None)

    if len(tc_indices.difference(range(len(tempo_changes)))) != 0:
        raise ValueError(
            "You put tempo changes that are not at the start of each bar, didn't you? This is a requirement. To "
            "bypass this, add a respectful time signature marker at your tempo change.")

    return tc_stuff
