# Melodex: a 5-minute visual tour

This is the fastest way to understand Melodex.

## 1. Add your music

Open **My music**.

![Empty My Music screen](images/my-music-empty.png)

Choose **Add folder…** and select a folder containing music you are authorised to play.

Melodex indexes the files in place. It does not need to move your original music.

## 2. Browse your library

![My Music populated with tracks](images/my-music-library.png)

Once indexed, your tracks appear in **My music**.

You can use Melodex as a normal player: select a track, play it, add things to the queue and browse your collection.

![My Music while a track is playing](images/my-music-playing.png)

The interesting part starts when you let Melodex help shape the session.

<a id="play-for-me"></a>
## 3. Play for Me

![Play for Me](images/play-for-me.png)

**Play for Me** asks three simple questions:

1. What kind of session do you want?
2. How long should it be?
3. How familiar or surprising should it feel?

The player uses local taste memory and available analysis to construct the journey.

## 4. Familiar ↔ Surprising

![Familiar to Surprising control](images/familiar-surprising.png)

Move toward **Familiar** when you want comfort and stronger known-positive signals.

Move toward **Surprising** when you want Melodex to take more chances.

This is not a permanent preference. It describes what you want *right now*.

<a id="teach-melodex-your-taste"></a>
## 5. Teach Melodex your taste

![Keep and Love controls](images/taste-controls.png)

A few signals are enough:

- **♥ Love** — strong positive feedback.
- **Keep** — this belongs in my musical world.
- **Finish the track** — useful positive evidence.
- **Skip early** — useful negative evidence.
- **Return later** — evidence that the track mattered.

A single skip is not treated as a permanent judgement. Context matters.

<a id="flow-not-shuffle"></a>
## 6. Flow, not shuffle

Shuffle asks:

> What random track comes next?

Flow asks:

> **What track makes sense after this one?**

When local audio analysis is available, Melodex can consider musical characteristics such as tempo, energy, key, loudness, timbre and structure.

Flow then tries to order the queue so the movement between tracks feels more deliberate.

A future version of this tour will show the same queue **before and after Flow** side-by-side.

## 7. Moments

![Moments](images/moments.png)

Sometimes the thing you want to remember is not a whole song.

Use **Save Moment** to remember an exact playback position: a bass entrance, lyric, solo, breakdown or transition.

## 8. Music sources

![Music Sources](images/sources.png)

The public version exposes a source-neutral system:

- **This computer** — your local files.
- **Jamendo** — the public reference provider.
- **Install `.mdxprovider`** — compatible desktop providers.
- **Provider Bridge** — authenticated access for other devices such as Android.

Melodex's queue, taste and Flow systems sit above those sources.

<a id="ask-melodex"></a>
## 9. Ask Melodex

![Ask Melodex](images/ask-melodex.png)

LLM support is optional.

Connect Ollama, OpenWebUI or another compatible model if you want to express listening intent in natural language.

Try:

> Keep this mood but make the next hour stranger.

> Give me a 45-minute session that starts familiar and gradually becomes more energetic.

> Rediscover something I liked but have not played recently.

You can still use the normal Melodex controls for all core listening features.

## Where next?

- [Why Melodex?](WHY_MELODEX.md)
- [Full user guide](USER_GUIDE.md)
- [Install on macOS](INSTALL_MACOS.md)
- [Install on Windows](INSTALL_WINDOWS.md)
- [Install on Android](INSTALL_ANDROID.md)
