let songData = []; // Array to hold song data from XML
let filteredData = []; // Array to hold filtered song data

document.addEventListener('DOMContentLoaded', () => {
    // Load song data from XML file(s)
    loadXMLData('path/to/your/input.xml', 'path/to/your/output.xml');

    // Add event listener for search bar
    document.getElementById('searchBar').addEventListener('keyup', searchSongs);
});

function loadXMLData(inputXMLPath, outputXMLPath) {
    // Fetch and parse XML data (you'd use actual paths in place of 'inputXMLPath' and 'outputXMLPath')
    // Populate songData and filteredData arrays
    // Render initial song list
}

function renderSongList() {
    const songListElem = document.getElementById('songList');
    songListElem.innerHTML = ''; // Clear existing list

    filteredData.forEach((song, index) => {
        const listItem = document.createElement('li');
        listItem.classList.add('list-group-item');
        listItem.textContent = song.title; // Assuming 'title' is a property in your song data
        listItem.addEventListener('click', () => showSongInfo(index));
        songListElem.appendChild(listItem);
    });
}

function showSongInfo(index) {
    const songInfoPanel = document.getElementById('songInfoPanel');
    const song = filteredData[index];
    
    // Display song info and similar songs with matching POIs in the panel
    // You'd build this out based on the structure of your song data
}

function searchSongs(event) {
    const query = event.target.value.toLowerCase();
    
    filteredData = songData.filter(song => song.title.toLowerCase().includes(query));
    renderSongList();
}