


/* ----------------------------------------------------------------------------------------------------
                                            Load Google Maps classes
   ---------------------------------------------------------------------------------------------------- */

(g=>{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={});var d=b.maps||(b.maps={}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src=`https://maps.${c}apis.com/maps/api/js?`+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))})({
    key: "{{ GOOGLE_MAPS_API_KEY }}",
    v: "weekly",
    // Use the 'v' parameter to indicate the version to use (weekly, beta, alpha, etc.).
    // Add other bootstrap parameters as needed, using camel case.
});


/* ----------------------------------------------------------------------------------------------------
                                  Map showing the location of the Cafe
   ---------------------------------------------------------------------------------------------------- */

let cafe_map;

async function initCafeMap() {

    // Request needed libraries.
    const { Map, InfoWindow } = await google.maps.importLibrary("maps");
    const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker",);

    /* Define the map view */
    const cafe_map = new Map(document.getElementById("cafe_map"), {
        restriction: {
            latLngBounds: {{ MAP_BOUNDS | tojson }},
            strictBounds: false,
        },
        zoom: 16,
        center: { lat: {{ cafe_map_coords['lat'] }}, lng: {{ cafe_map_coords['lng'] }} },
        mapId: "7499929d658a3166",
    });

    /* This is our set of cafes */
    const cafes = {{ cafes | tojson }}

    // Create an info window to share between markers.
    const infoWindow = new InfoWindow();

    // Create the markers.
    cafes.forEach( ({ position, title, color }, i) => {
        const pin = new PinElement({
        glyph: `${i + 1}`,
        });

        const marker = new AdvancedMarkerElement({
            position,
            map: cafe_map,
            title: `${title}`,
            content: new PinElement({
                            background: color,
                            borderColor: "black",
                            glyphColor: "black",
                        }).element
        });

        // Add a click listener for each marker, and set up the info window.
        marker.addListener("click", ({ domEvent, latLng }) => {
            const { target } = domEvent;
            infoWindow.close();
            infoWindow.setContent(marker.title);
            infoWindow.open(marker.map, marker);
        });
    });
}

initCafeMap();


/* ----------------------------------------------------------------------------------------------------
                                 Map for the Routes Passing the Cafe
   ---------------------------------------------------------------------------------------------------- */

let gpx_map;

async function initGpxMap() {

    /* Request needed libraries */
    const { Map, InfoWindow } = await google.maps.importLibrary("maps");
    const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker",);

    /* Define the map view */
    const map = new Map(document.getElementById("gpx_map"), {
        restriction: {
            latLngBounds: {{ MAP_BOUNDS | tojson }},
            strictBounds: false,
        },
        zoom: 9,
        center: { lat: {{ midlat }}, lng: {{ midlon }} },
        mapId: "7499929d658a3166",
    });

    /* Loop over Polylines */
    {% for polyline in polylines %}

        /* Define our polyline */
        const flightPath{{loop.index}} = new google.maps.Polyline({
            path: {{ polyline['polyline'] }},
            geodesic: true,
            strokeColor: "{{ polyline['color'] }}",
            strokeOpacity: 1.0,
            strokeWeight: 4,
        });

        /* We want a pop up info box for thr GPX route */
        google.maps.event.addListener(flightPath{{loop.index}}, 'mouseover', function(event) {
            current_lat = event.latLng.lat();
            current_lon = event.latLng.lng();

            // Create a new InfoWindow.
            gpxInfoWindow{{loop.index}} = new google.maps.InfoWindow({
                content: '{{ polyline['name'] | safe }}',
                position: event.latLng,
            });

            gpxInfoWindow{{loop.index}}.open(map);
        });

        /* and close the info box when they move elsewhere */
        google.maps.event.addListener(flightPath{{loop.index}}, 'mouseout', function() {
            gpxInfoWindow{{loop.index}}.close();
        });

        /* Add the path to the map */
        flightPath{{loop.index}}.setMap(map);

    {% endfor %}

    /* This is our set of cafes */
    const cafes = {{ cafes | tojson }}

    // Create an info window to share between markers.
    const infoWindow = new InfoWindow();

    // Create the markers.
    cafes.forEach( ({ position, title, color }, i) => {
        const pin = new PinElement({
        glyph: `${i + 1}`,
        });

        const marker = new AdvancedMarkerElement({
            position,
            map,
            title: `${title}`,
            content: new PinElement({
                            background: color,
                            borderColor: "black",
                            glyphColor: "black",
                        }).element
        });

        // Add a click listener for each marker, and set up the info window.
        marker.addListener("click", ({ domEvent, latLng }) => {
            const { target } = domEvent;
            infoWindow.close();
            infoWindow.setContent(marker.title);
            infoWindow.open(marker.map, marker);
        });
    });
}

initGpxMap();


/* ----------------------------------------------------------------------------------------------------
                                        Activate jQuery on the Tables
   ---------------------------------------------------------------------------------------------------- */

$(document).ready( function () {
    $('#gpxTable').DataTable({

        pageLength: 20,
        "autoWidth": false,

    })
} );

