import collections
import markovify
import bintrees
import requests
import imageio
import moviepy.editor
import random
import psutil
import config
import tqdm
import json
import sys
import re
import os
imageio.plugins.ffmpeg.download()

def _watson_transcript(filename):
    tfilename = os.path.join('transcripts', os.path.basename(filename) + '.json')

    try:
        return json.load(open(tfilename))
    except IOError:
        try:
            r = requests.post(
                'https://stream.watsonplatform.net/speech-to-text/api/v1/recognize?word_confidence=true&timestamps=true&model=en-US_NarrowbandModel&speaker_labels=true',
                data=open(filename),
                headers={'Content-Type': 'audio/mp3'},
                auth=config.watson_creds
            )
        except:
            print "CATASTROPHIC FAILURE. Ping admins on IRC. Seriously."
            sys.exit(1)
        with open(tfilename, 'w') as t:
            t.write(r.content)
        return r.json()

def _float_to_ts(f):
    microseconds = int((f-int(f))*1000)
    seconds = int(f) % 60
    minutes = (int(f) / 60) % 60
    hours = (int(f) / 60 / 60) % 60
    return '%02i:%02i:%02i.%03i' % (hours, minutes, seconds, microseconds)

def available_words(base_dir):
    return set(os.listdir(base_dir)) - { '%hesitation' }

def make_model(transcript_dir):
    sentences = [ ]
    for jfile in os.listdir(transcript_dir):
        j = json.load(open(os.path.join(transcript_dir, jfile)))
        for r in j['results']:
            for a in r['alternatives']:
                sentences.append(str(a['transcript'].lower().replace('%hesitation', '')).strip().strip('.')+'.')
    text_model = markovify.NewlineText('\n'.join(sentences) + '\n')
    return text_model

def make_sentences(transcripts_dir, base_dir, output_file, num_sentences, min_chars=64, maximum_chars=128):
    m = make_model(transcripts_dir)
    w = available_words(base_dir)
    sentences = [ ]
    t = tqdm.tqdm(total=num_sentences)
    while len(sentences) < num_sentences:
        s = m.make_short_sentence(maximum_chars).strip('.')
        if len(s) < min_chars:
            continue
        missing = set(s.split()) - w
        if not missing:
            t.update(1)
            sentences.append(s)
        #else:
        #   print "MISSING:", missing
    with open(output_file, "w") as o:
        o.write("\n".join(sentences) + '\n')
    return sentences

def audio_to_words(filename, word_confidence_threshold=0.98, speaker_confidence_threshold=0.3):
    transcript = _watson_transcript(filename)
    speakers = bintrees.AVLTree({ v['from']: v for v in transcript['speaker_labels'] })
    for r in transcript['results']:
        timestamps = r['alternatives'][0]['timestamps']
        confidences = r['alternatives'][0]['word_confidence']
        for (w,ta,tb), (w_,c) in zip(timestamps, confidences):
            assert w == w_
            from_ts = _float_to_ts(ta)
            to_ts = _float_to_ts(tb)
            speaker_label = speakers.floor_item(ta)[1]
            if _float_to_ts(speaker_label['to']) < from_ts:
                speaker_confidence = 0
                speaker = -1
            else:
                speaker = speaker_label['speaker']
                speaker_confidence = speaker_label['confidence']
            if c > word_confidence_threshold and speaker_confidence > speaker_confidence_threshold:
                yield w.lower().strip('.'), from_ts, to_ts, speaker, speaker_confidence

def extract_audiofile(filename):
    afilename = os.path.join('audios', os.path.basename(filename) + '.mp3')
    if not os.path.exists(afilename):
        print "Extracting", afilename
        v = moviepy.editor.VideoFileClip(filename)
        v.audio.write_audiofile(afilename)
    return afilename

def video_to_words(filename, **kwargs):
    afilename = extract_audiofile(filename)
    return audio_to_words(afilename, **kwargs)


def vtt_to_words(filename):
    old_start = None
    old_word = None
    new_start = None
    new_word = None

    for line in open(filename):
        if '-->' in line:
            new_start = line.split()[0]
            if old_word is not None:
                yield old_word.lower(), old_start, new_start
            old_start = new_start
        elif '<c>' in line:
            # first get the first word
            line = re.sub(r'<c.color......>', '', line)
            old_word = line.split("<")[0].strip()
            words = re.findall(r'\d\d:\d\d:\d\d\.\d\d\d><c> \w+</c>', line)
            for w in words:
                new_start, new_word = w.replace("<c>","").replace("</c>","").replace(">","").split()
                yield old_word.lower(), old_start, new_start
                old_word = new_word
                old_start = new_start

def _fork_wrapped(f):
    def wrapped_f(*args, **kwargs):
        p = os.fork()
        if p == 0:
            f(*args, **kwargs)
            for c in psutil.Process(os.getpid()).children(recursive=True):
                c.kill()
            os.kill(os.getpid(), 9)
            sys.exit(0)
        else:
            os.wait()
    return wrapped_f

@_fork_wrapped
def extract_clip(src_file, dst_file, ta, tb):
    v = moviepy.editor.VideoFileClip(src_file)
    word_audio = v.audio.cutout(tb, v.duration).cutout('00:00:00.000', ta)
    word_video = v.cutout(tb, v.duration).cutout('00:00:00.000', ta).set_audio(word_audio)
    word_video.write_videofile(dst_file)

@_fork_wrapped
def extract_audio(src_file, dst_file, ta, tb):
    a = moviepy.editor.AudioFileClip(src_file)
    word_audio = a.cutout(tb, a.duration).cutout('00:00:00.000', ta)
    word_audio.write_audiofile(dst_file)

def split_audio(audio_file, dst_dir, vtt_file=None):
    for word, ta, tb, speaker, sc in vtt_to_words(vtt_file) if vtt_file is not None else audio_to_words(audio_file):
        print "Extracting word: %s" % word
        dst_file = os.path.join(dst_dir, word, os.path.basename(audio_file+'-'+ta.replace(':','.')+'-'+str(speaker)+'-'+str(sc)+'.mp3'))
        if os.path.exists(dst_file):
            continue
        try: os.makedirs(os.path.join(dst_dir, word))
        except OSError: pass
        extract_audio(audio_file, dst_file, ta, tb)

def split_clip(video_file, dst_dir, vtt_file=None):
    for word, ta, tb, speaker, sc in vtt_to_words(vtt_file) if vtt_file is not None else video_to_words(video_file):
        print "Extracting word: %s" % word
        dst_file = os.path.join(dst_dir, word, os.path.basename(video_file+'-'+ta.replace(':','.')+'-'+str(speaker)+'-'+str(sc)+'.mp4'))
        if os.path.exists(dst_file):
            continue
        try: os.makedirs(os.path.join(dst_dir, word))
        except OSError: pass
        extract_clip(video_file, dst_file, ta, tb)

def audio_list(base_dir, words):
    return [ moviepy.editor.AudioFileClip(os.path.join(base_dir, w, random.choice(os.listdir(os.path.join(base_dir, w))))) for w in words ]

def check_attempt(base_dir, dst_file, words, attempt_file, num_examples=16):
    print "Generating validation data..."
    alist = [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]
    good_times = [ ]
    bad_times = [ ]

    for _ in tqdm.tqdm(range(num_examples)):
        gs = _float_to_ts(moviepy.editor.concatenate_audioclips(alist).duration)
        alist += [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]
        alist += audio_list(base_dir, words)
        alist += [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]
        ge = _float_to_ts(moviepy.editor.concatenate_audioclips(alist).duration)
        good_times.append([gs, ge])

        alist += [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]

        bs = _float_to_ts(moviepy.editor.concatenate_audioclips(alist).duration)
        alist += [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]
        alist += [ moviepy.editor.AudioFileClip(attempt_file) ]
        alist += [ moviepy.editor.AudioFileClip(os.path.join(os.path.dirname(os.path.dirname(__file__)), "silence.mp3")) ]
        be = _float_to_ts(moviepy.editor.concatenate_audioclips(alist).duration)
        bad_times.append([bs, be])

    #print good_times
    #print bad_times

    print "Writing validation data..."
    moviepy.editor.concatenate_audioclips(alist).write_audiofile(dst_file)

    print "Analyzing validation data..."
    good_speakers = collections.Counter()
    bad_speakers = collections.Counter()
    bad_words = [ ]
    for word, ta, _, speaker, _ in audio_to_words(dst_file, word_confidence_threshold=0, speaker_confidence_threshold=0):
        if ta < '00.01.00.000': # ibm says the first 30 seconds are garbage, and it gets good after a minute
            continue
        elif any(ta >= gs and ta <= ge for gs,ge in good_times):
            #print "Adam word:", word, ta, speaker
            good_speakers[speaker] += 1
        elif any(ta >= bs and ta <= be for bs,be in bad_times):
            #print "Your word:", word, ta, speaker
            bad_speakers[speaker] += 1
            if ta >= bad_times[-1][0]:
                bad_words.append(word)
        else:
            #print "Ignoring:", word, ta, speaker
            continue

    success = True

    #print good_speakers
    #print bad_speakers
    print "Classification complete."
    print "... our ground truth (Adam) speaker classification confidences:", dict(good_speakers)
    print "... our candidate (you, but hopefully Adam!) speaker classification confidences:", dict(bad_speakers)
    if good_speakers.most_common(1)[0][0] != bad_speakers.most_common(1)[0][0]:
        success = False
        print "FAIL: you are not Adam!"

    #missing_words = set(words) - set(bad_words)
    #new_words = set(bad_words) - set(words)
    common_words = set(bad_words) & set(words)
    #print len(common_words), len(words), len(words) * 0.66
    if len(common_words) < len(words) * 0.66:
        success = False
        print "FAIL: you didn't say the right thing (we heard: \"%s\")!" % " ".join(bad_words)

    if success:
        print "SUCCESS!"

    return success

def build_clip(base_dir, dst_file, words):
    word_clips = [ ]
    for w in words:
        word_clips.append(moviepy.editor.VideoFileClip(os.path.join(base_dir, w, random.choice(os.listdir(os.path.join(base_dir, w))))))
    moviepy.editor.concatenate_videoclips(word_clips).write_videofile(dst_file)

def build_audio(base_dir, dst_file, words):
    word_clips = [ ]
    for w in words:
        word_clips.append(moviepy.editor.AudioFileClip(os.path.join(base_dir, w, random.choice(os.listdir(os.path.join(base_dir, w))))))
    moviepy.editor.concatenate_audioclips(word_clips).write_audiofile(dst_file)

if __name__ == '__main__':
    if sys.argv[1] == 'extract_audio':
        for d in sys.argv[2:]:
            extract_audiofile(d)
    if sys.argv[1] == 'transcribe_video':
        for d in sys.argv[2:]:
            list(video_to_words(d))
    if sys.argv[1] == 'transcribe_audio':
        for d in sys.argv[2:]:
            list(audio_to_words(d))
    if sys.argv[1] == 'unpack_video':
        for d in sys.argv[3:]:
            split_clip(d, sys.argv[2])
    if sys.argv[1] == 'unpack_audio':
        for d in sys.argv[3:]:
            split_audio(d, sys.argv[2])
    elif sys.argv[1] == 'build':
        build_clip(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == 'build_audio':
        build_audio(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == 'sentences':
        make_sentences(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif sys.argv[1] == 'check':
        #def check_attempt(base_dir, dst_file, words, attempt_file, num_examples=32):
        sys.exit(0 if check_attempt(sys.argv[2], sys.argv[3], sys.argv[5:], sys.argv[4]) else 1)
