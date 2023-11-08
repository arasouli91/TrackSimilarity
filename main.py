from operator import itemgetter
import argparse
import os
import xml.etree.ElementTree as ET
from scipy.spatial.distance import cosine, euclidean
from fastdtw import fastdtw
import librosa
from sklearn.metrics.pairwise import cosine_similarity
from xml.etree.ElementTree import ElementTree, Element, SubElement

class Song:
    def __init__(self, file_path, key, bpm, duration):
        self.file_path = file_path
        self.key = key
        self.bpm = bpm
        self.duration = duration
        self.buildup_segments = []
        self.drop_segments = []
        self.buildup_segments_features = []
        self.drop_segments_features = []

    def add_buildup_segment(self, buildup_time, buildup_name, drop_time, drop_name):
        self.buildup_segments.append(Segment(buildup_time, drop_time, buildup_name))

    def add_drop_segment(self, drop_time, drop_name, end_time):
        self.drop_segments.append(Segment(drop_time, end_time, drop_name))

class Segment:
    def __init__(self, start_time, end_time, poi_name):
        self.start_time = start_time
        self.end_time = end_time
        self.poi_name = poi_name

def main(xml_file_path, bpm_threshold, similarity_threshold, start_offset):
    print(f"XML file path: {xml_file_path}")
    print(f"BPM threshold: {bpm_threshold}")
    print(f"Similarity threshold: {similarity_threshold}")
    print(f"Start offset: {start_offset}")

    # Get song details from the XML file
    song_details = get_song_details(xml_file_path)
    print(f"Total songs in song_details: {len(song_details)}")

    # Storing similarity scores and details for later use
    similarity_results = []

    calculate_features_for_all_songs(song_details)

    # Iterate over all pairs of songs
    for i, song1 in enumerate(song_details[start_offset:], start=start_offset):
        if (i+1)%50==0:
            print(f"Processed {i} songs against all others")
            user_input = input("Do you want to continue? (y/n): ")
            if user_input.lower() != 'y':
                break
            print("Continuing...")
        for j, song2 in enumerate(song_details):
            if i >= j:
                continue
            
            # Check key compatibility and BPM difference
            if not compatible_keys(song1.key, song2.key):# or abs(song1.bpm - song2.bpm) > bpm_threshold:
                continue
            
            # Process both the buildup-drop pairs and the standalone drops
            compare_segments(similarity_results, 'buildup_segments', song1, song2)
            compare_segments(similarity_results, 'drop_segments', song1, song2)

    # Sorting similarity results in descending order of similarity score
    similarity_results.sort(key=itemgetter('similarity'), reverse=True)
    
    # Creating or reading the root XML element
    output_file_path = 'output.xml'
    # if os.path.exists(output_file_path):
    #     tree = ElementTree()
    #     tree.parse(output_file_path)
    #     root = tree.getroot()
    # else:
    root = Element('Songs')

    # Collect existing song pair entries in the XML file to prevent duplicate entries during the update.
    # Not actually making song pairs anymore, just rewriting all of xml
    existing_entries = {(song.get('FilePath'), song.find('./Song').get('FilePath') if song.find('./Song') else None) for song in root.findall('Song')}
    
    write_xml_results(similarity_results, existing_entries, root, similarity_threshold)

    # Write the output XML to a file
    indent_xml(root)
    tree = ElementTree(root)
    tree.write(output_file_path)

    # Print the highest similarity scores
    #for result in similarity_results[:100]:  # Adjust the number of results to print as needed
    #print(f"Similarity: {result['similarity']:.2f}, Song1: {result['song1']['file_path']}, POI1: {result['poi1']}, Song2: {result['song2']['file_path']}, POI2: {result['poi2']}")

def write_xml_results(similarity_results, existing_entries, root, similarity_threshold):
    for result in similarity_results:
        if result['similarity'] < similarity_threshold:
            continue

        song1_path, song2_path = result['song1_path'], result['song2_path']
        match_type = result['match_type']
        poi1_name, poi2_name = result['poi1_name'], result['poi2_name']
        poi1_time, poi2_time = result['poi1_time'], result['poi2_time']

        if song1_path not in existing_entries:
            # Look for an existing Song element in the XML
            song_elem = root.find('./Song[@FilePath="{}"]'.format(song1_path))

            if song_elem is None:
                # If song1 elem does not exist yet, create new Song element
                song_elem = SubElement(root, 'Song', FilePath=song1_path)
                existing_entries.add(song1_path)
            
            match_elem = SubElement(song_elem, 'Match', MatchType=match_type, Similarity=f"{int(result['similarity']*100)}%")
            SubElement(match_elem, 'Poi', Name=poi1_name, Pos=str(poi1_time))

            similar_song_elem = SubElement(match_elem, 'Song', FilePath=song2_path)
            SubElement(similar_song_elem, 'Poi', Name=poi2_name, Pos=str(poi2_time))

def compare_segments(similarity_results, segment_type, song1, song2):
    segment_list1 = getattr(song1, segment_type)
    segment_list2 = getattr(song2, segment_type)
    features1 = getattr(song1, f"{segment_type}_features")
    features2 = getattr(song2, f"{segment_type}_features")

    for segment1 in segment_list1:
        segment_list1 = getattr(song1, segment_type)
        segment_list2 = getattr(song2, segment_type)
        features1_list = getattr(song1, f"{segment_type}_features")
        features2_list = getattr(song2, f"{segment_type}_features")

        for i, segment1 in enumerate(segment_list1):
            features1 = features1_list[i]  # Assume that features are precalculated and stored in the list
            for j, segment2 in enumerate(segment_list2):
                features2 = features2_list[j]  # Assume that features are precalculated and stored in the list

                similarity = calculate_similarity(features1, features2)
                
                match_type = "Build" if segment_type == "buildup_segments" else "Drop"

                similarity_results.append({
                    'song1_path': song1.file_path,
                    'song2_path': song2.file_path,
                    'poi1_name': segment1.poi_name,
                    'poi2_name': segment2.poi_name,
                    'poi1_time': segment1.start_time,
                    'poi2_time': segment2.start_time,
                    'similarity': similarity,
                    'match_type': match_type
                })

def get_song_details(xml_file_path):
    tree = ET.parse(xml_file_path)
    root = tree.getroot()

    song_details = []

    count = 0
    for song_elem in root.findall('Song'):
        if count%100==0: 
            print(f"Proccessed {count} song elements")
        count+=1
        # Get the basic details of the song
        file_path = song_elem.get('FilePath')
        scan_elem = song_elem.find('Scan')
        #song_info = song_elem.find('Infos')

        if not os.path.exists(file_path) or scan_elem is None:
            print(f"Skipping song {file_path} due to missing information")
            # Skip to the next song if the file does not exist, no key/bpm/duration exists
            continue  

        key = scan_elem.get('Key')
        # the bpm in scan elem is actually not right? it should be in the beatgrid poi
        #bpm = float(scan_elem.get('Bpm')) * 60  # Converting from beats per second to beats per minute

        # Create a Song instance
        song = Song(file_path, key, 0, 0)

        # Identifying and pairing up build-up and drop POIs
        pois = song_elem.findall('Poi')
        buildups = [(float(poi.get('Pos')), poi.get('Name')) for poi in pois if 'Buildup' in (poi.get('Name') or '')]
        drops = [(float(poi.get('Pos')), poi.get('Name')) for poi in pois if 'End Break' in (poi.get('Name') or '')]
        
        if len(drops) == 0 and len(buildups) == 0:
            continue
        
        # Pairing buildups with drops to get the buildup segment
        for (buildup, buildup_name), (drop, drop_name) in zip(buildups, drops):
            song.add_buildup_segment(buildup, buildup_name, drop, drop_name)

        for drop, drop_name in drops[len(buildups):]:
            song.add_drop_segment(drop, drop_name, drop + 4)

        song_details.append(song)

    return song_details

def get_features(file_path, start, end):
    try:
        # Function to get features from a segment of a song
        y, sr = librosa.load(file_path, sr=None, offset=start, duration=end-start)
        
        # Calculate MFCC and Chroma features
        mfcc = librosa.feature.mfcc(y=y, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        
        return mfcc, chroma
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return None

def calculate_similarity(features1, features2):
    # Function to calculate similarity between features of two segments
    mfcc1, chroma1 = features1
    mfcc2, chroma2 = features2

    # Calculating similarity using various metrics
    mfcc_similarity = cosine_similarity(mfcc1.T, mfcc2.T).mean()
    chroma_similarity = cosine_similarity(chroma1.T, chroma2.T).mean()
    
    distance, path = fastdtw(mfcc1.T, mfcc2.T, dist=euclidean)
    dtw_similarity = 1.0 / (1.0 + distance)

    # Combining the similarity measures to get a single score
    combined_similarity = (mfcc_similarity + chroma_similarity + dtw_similarity) / 3

    return combined_similarity

def calculate_features_for_all_songs(song_details):
    for song in song_details:
        for segment in song.buildup_segments:
            features = get_features(song.file_path, segment.start_time, segment.end_time)
            if features:
                song.buildup_segments_features.append(features)

        for segment in song.drop_segments:
            features = get_features(song.file_path, segment.start_time, segment.end_time)
            if features:
                song.drop_segments_features.append(features)

def compatible_keys(key1, key2):
    circle_of_fifths_major = {
        'C': ['A', 'G', 'D'],
        'G': ['E', 'D', 'A'],
        'D': ['B', 'A', 'E'],
        'A': ['F#m', 'E', 'B'],
        'E': ['C#m', 'B', 'F#'],
        'B': ['G#m', 'F#', 'C#'],
        'F#': ['D#m', 'C#', 'G#'],
        'C#': ['A#m', 'G#', 'D#'],
        'F': ['Dm', 'Bb', 'C'],
        'Bb': ['Gm', 'C', 'F'],
        'Eb': ['Cm', 'F', 'Bb'],
        'Ab': ['Fm', 'Bb', 'Eb'],
        'Db': ['Bbm', 'Eb', 'Ab'],
        'Gb': ['Ebm', 'Ab', 'Db'],
        'Cb': ['Abm', 'Db', 'Gb'],
    }
    
    circle_of_fifths_minor = {
        'Am': ['C', 'Em', 'Dm'],
        'Em': ['G', 'Bm', 'Am'],
        'Bm': ['D', 'F#m', 'Em'],
        'F#m': ['A', 'C#m', 'Bm'],
        'C#m': ['E', 'G#m', 'F#m'],
        'G#m': ['B', 'D#m', 'C#m'],
        'D#m': ['F#', 'A#m', 'G#m'],
        'A#m': ['C#', 'Fm', 'D#m'],
        'Dm': ['F', 'Gm', 'Am'],
        'Gm': ['Bb', 'Cm', 'Dm'],
        'Cm': ['Eb', 'Fm', 'Gm'],
        'Fm': ['Ab', 'Bbm', 'Cm'],
        'Bbm': ['Db', 'Ebm', 'Fm'],
        'Ebm': ['Gb', 'Abm', 'Bbm'],
        'Abm': ['Cb', 'Gb', 'Ebm'],
    }
    
    # Check if the keys are identical
    if key1 == key2:
        return True
    
    # Check if the keys are in the compatible keys list of each other
    if key1 in circle_of_fifths_major:
        return key2 in circle_of_fifths_major[key1]
    
    if key1 in circle_of_fifths_minor:
        return key2 in circle_of_fifths_minor[key1]
    
    return False

def indent_xml(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_xml(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-f', '--xml_file_path', type=str, default=r'C:\Users\v-arasouli\AppData\Local\VirtualDJ\database.xml', help='Path to the XML file')
    parser.add_argument('-b', '--bpm_threshold', type=int, default=8, help='BPM threshold')
    parser.add_argument('-s', '--similarity_threshold', type=float, default=0.4, help='Similarity threshold')
    parser.add_argument('-o', '--start_offset', type=int, default=0, help='Start offset for song enumeration')
    
    args = parser.parse_args()
    main(args.xml_file_path, args.bpm_threshold, args.similarity_threshold, args.start_offset)
    #D:\VirtualDJ\database.xml