# MIDI to FnF

Very "useful" MIDI to fnf chart converter

## NOTES

Listens to each note and blah blah blah idk

## BPM CHANGES

BPM changes must be instant **(be a snap)** and can only be positioned at the end of each bar (also accounting for time signature changes). The program will reject MIDI files that violate this.

## TIME SIGNATURE CHANGES

There is a proper way to handle time signatures... but we have some rules
with the MIDI. Time signature changes are handled by time signature change markers in FL Studio.

1. The denominator for all time signatures **must** be 4. The program will refuse MIDIs if anywhere has its time
   signature be any value but 4. Always round down to 4/4. This means:
   - `6/8 -> 4/4` (For sheet music, that would be equivalent to cramming triplets)
   - `7/8 -> 3.5/4`; in this case you need an 8/4 marker once every 7 beats
   - `2/2 -> 4/4`
   - `13/8 -> 6.5/4`; in this case you need a 7/4 marker once every 6.5 beats

2. You may place markers anywhere you like, with this **one caveat:** you MUST sixteenth-note align it (this is an FL
   Studio step). If the beat of any tempo marker is not divisible by $1/16$ the program will refuse the MIDI.
3. If a marker is not placed at the start of where a bar should be (e.g. song starts off at 4/4, marker placed at beat
   7), the last "partial bar" before the time signature change will be cut off. In the previous example, it would be
   treated as 4/4 at beat 0, 3/4 at beat 4, 4/4 at beat 7. Note that I count from 0, FL Studio counts from 1. As stated
   before, **this is the only way to achieve decimal time signature changes.**

## COALESCING EVENTS

**TOGGLE**

Events may be coalesced if they occur at the same time (no need to worry about floating point imprecision, there is tolerance)

Whenever events are coalesced, the order at which the events will be put in will be in the same order
they are declared by the listeners.
