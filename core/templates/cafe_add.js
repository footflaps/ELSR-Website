// JS Module for adding or editing a cafe


// Triggered by 'Locate Me' button
function locateMe() {

    // Can we get the user location?
    if (navigator.geolocation) {

        alert("Before");
        navigator.geolocation.getCurrentPosition(fillInForm);
        alert("After");

    } else {

        // Dear John letter
        alert("Geolocation is not supported by this browser.");

    }
};


(g=>{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={});var d=b.maps||(b.maps={}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src=`https://maps.${c}apis.com/maps/api/js?`+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))})({
    key: "{{ GOOGLE_MAPS_API_KEY }}",
    v: "weekly",
    // Use the 'v' parameter to indicate the version to use (weekly, beta, alpha, etc.).
    // Add other bootstrap parameters as needed, using camel case.
});

let map;
let infoWindow;

async function initMap() {

    // Request needed libraries.
    const { Map, InfoWindow } = await google.maps.importLibrary("maps");
    const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker",);

    map = new Map(
        document.getElementById("map"), {
            restriction: {
                latLngBounds: {{ MAP_BOUNDS | tojson }},
                strictBounds: false,
            },
            zoom: 10,
            center: {{ ELSR_HOME | tojson }},
        }
    );

    // Create the initial InfoWindow.
    infoWindow = new InfoWindow({
        content: "Locate the cafe on the map and click to transfer the coordinates to the form below.",
        position: {{ ELSR_HOME | tojson }},
    });

    infoWindow.open(map);

    // Configure the click listener.
    map.addListener("click", (mapsMouseEvent) => {

        // Close the current InfoWindow.
        infoWindow.close();

        // Populate the form
        document.getElementById("lat").value = mapsMouseEvent.latLng.lat();
        document.getElementById("lon").value = mapsMouseEvent.latLng.lng();

        // Create a new InfoWindow.
        infoWindow = new google.maps.InfoWindow({
            position: mapsMouseEvent.latLng,
        });

        infoWindow.setContent(
            "Form has been updated",
        );

        infoWindow.open(map);

    });

}

initMap();



$(document).ready( function () {

    if ( document.getElementById("lat").value == "" ) {
        document.getElementById("lat").value = "Click on map above to populate";
        document.getElementById("lon").value = "Click on map above to populate"; }

})



// Fill the form in with the position
function fillInForm(position) {

    alert("sub")

    // Update the form
    document.getElementById("lat").value = position.coords.latitude;
    document.getElementById("lon").value = position.coords.longitude;

    // Update zoom and focus of Google Maps
    map.zoom = 18;
    map.setCenter(new google.maps.LatLng(position.coords.latitude, position.coords.longitude));
    google.maps.event.trigger(map, 'zoom_changed');

    // Move and update infoWindow
    infoWindow.setOptions({ position: new google.maps.LatLng(position.coords.latitude, position.coords.longitude)});
    infoWindow.setContent("Form has been updated");

}