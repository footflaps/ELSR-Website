// JS Module for validating ride entry

// The form elements we will be using
let date = document.getElementById('date');
let start_time = document.getElementById('start_time');
let meeting_point = document.getElementById('start_location');
let new_start = document.getElementById('other_location');
let destination = document.getElementById('destination');
let new_destination = document.getElementById('new_destination');
let gpx = document.getElementById('gpx_name');
let gpx_file = document.getElementById('gpx_file');


/* ****************************************************************************************************************
                                               Functions
  **************************************************************************************************************** */

function findLableForControl(el) {
   var idVal = el.id;
   labels = document.getElementsByTagName('label');
   for( var i = 0; i < labels.length; i++ ) {
      if (labels[i].htmlFor == idVal)
           return labels[i];
   }
}


// Get day of week from date
function getDayName(dateStr) {
    var date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', { weekday: 'long' });
}


// Check for date being in the past (in terms or days)
function dateInPast(dateStr) {
    var date = new Date(dateStr);
    var now = new Date();
    now.setHours(0,0,0,0);
    //alert(`date = ${date}, now = ${now}`)
    return date < now;
}


// Check date logic
function dateLogic() {

    // Is date set?
    if (date.value != "") {

         // Date must be in the future, unless admin
        if ( "{{ current_user.admin() }}" != "True" ) {
            if ( dateInPast(date.value) ) {

                // Disable Submit button and warn user
                document.getElementById("submit").disabled=true;
                document.getElementById("error").innerHTML="Date is in the past!"
                return;

            }
        }

        // Enable the Add Ride button as they have set a valid date
        document.getElementById("submit").disabled=false;
        document.getElementById("error").innerHTML=""

    }

}


// Autocomplete start time and location
function autoCompleteStart() {

    // date.value has form '2023-11-04', so convert to day of week eg 'Saturday' etc
    let day_of_week = getDayName(date.value);

    // Look up the default start time
    let default_start_time = {{ DEFAULT_START_TIMES | tojson }}[day_of_week]

    // Populate the form
    start_time.value = default_start_time['time'];
    meeting_point.value = default_start_time['location'];
    new_start.value = default_start_time['new'];

    // If we set 'Other' we need to unhide the new box
    if ( meeting_point.value == "{{ MEETING_OTHER }}" ) {

        // Show new start box and label
        new_start.style.display = "";
        findLableForControl(new_start).style.display = "";

    } else {

        // Hide new start box and label
        new_start.style.display = "none";
        findLableForControl(new_start).style.display = "none";

    }

    // Set colour back to white
    date.style.backgroundColor = 'white';

}


// Check logic of Meeting Point and New Meeting point
function meetingLogic() {

    // If they select the Other option, then they must specific the location
    if ( meeting_point.value == "{{ MEETING_OTHER }}" ) {

        // Need to specify what Other is
        if ( new_start.value.trim() == "" ) {

            // New start is not specified
            document.getElementById("submit").disabled=true;
            document.getElementById("error").innerHTML="Must define new meeting point!";
            new_start.style.backgroundColor = '#ffe6e6';

        } else {

            // Looks ok
            document.getElementById("submit").disabled=false;
            document.getElementById("error").innerHTML="";
            new_start.style.backgroundColor = 'white';

        }

    } else {

        // Clear new meeting point
        new_start.value = "";
        new_start.style.backgroundColor = 'white';

    }

}


// Check logic for destination cafe
function destinationLogic() {

    // If they select the New Cafe option then they must name it
    if ( destination.value == "{{ NEW_CAFE }}" ) {

        // They must specify new cafe
        if ( new_destination.value.trim() == "" ) {

            // New start is not specified
            document.getElementById("submit").disabled=true;
            document.getElementById("error").innerHTML="Must define the destination cafe!";
            new_destination.style.backgroundColor = '#ffe6e6';


        } else {

            // Looks ok
            document.getElementById("submit").disabled=false;
            document.getElementById("error").innerHTML="";
            new_destination.style.backgroundColor = 'white';

        }

    } else {

        // Clear new meeting point
        new_destination.value = "";
        new_destination.style.backgroundColor = 'white';

    }

}


// GPX file logic
function gpxLogic() {

    // If they select the Upload own route option then they must have selected a file
    if ( gpx.value == "{{ UPLOAD_ROUTE }}" ) {

        // Selected to upload a GPX
        if ( gpx_file.value == "" ) {

            // New start is not specified
            document.getElementById("submit").disabled=true;
            document.getElementById("error").innerHTML="Must upload a GPX file!";
            gpx.style.backgroundColor = '#ffe6e6';
            gpx_file.style.backgroundColor = '#ffe6e6';

        } else if ( gpx_file.value.split('.').pop().toLowerCase() != "gpx" ) {

            // Not GPX
            document.getElementById("submit").disabled=true;
            document.getElementById("error").innerHTML="File must be a '.gpx'.";
            gpx.style.backgroundColor = '#ffe6e6';
            gpx_file.style.backgroundColor = '#ffe6e6';

        } else {

            // Looks ok
            document.getElementById("submit").disabled=false;
            document.getElementById("error").innerHTML="";
            gpx.style.backgroundColor = 'white';
            gpx_file.style.backgroundColor = 'white';

        }

    } else {

        // Selected an existing GPX file
        // Clear file value
        gpx_file.value = "";
        gpx.style.backgroundColor = 'white';
        gpx_file.style.backgroundColor = 'white';

    }

}


// Run all out tests in sequence
function runlogic() {

    // Setting the date is most important
    dateLogic();

    // Only go any further if previous tests passed
    if ( document.getElementById("error").innerHTML == "" ) {
        meetingLogic();
    }

    // Only go any further if previous tests passed
    if ( document.getElementById("error").innerHTML == "" ) {
        destinationLogic();
    }

    // Only go any further if previous tests passed
    if ( document.getElementById("error").innerHTML == "" ) {
        gpxLogic();
    }

}


/* ****************************************************************************************************************
                                                 Onchange Handlers
  **************************************************************************************************************** */


// Trap user changing the meeting point
meeting_point.onchange = function() {

    if ( meeting_point.value == "{{ MEETING_OTHER }}" ) {

        // Show new start box and label
        new_start.style.display = "";
        findLableForControl(new_start).style.display = "";

    } else {

        // Hide New Start Location
        new_start.style.display = "none";
        findLableForControl(new_start).style.display = "none";

    }

    meetingLogic();
    runlogic();
}


// Trap user editing New meeting point
new_start.onchange = function() {

    // If they enter a new destination, swap selector to Other
    if ( new_start.value.trim() != "" ) {
        meeting_point.value = "{{ MEETING_OTHER }}";
    }

    meetingLogic();
    runlogic();
}


// Trap user editing destination
destination.onchange = function() {

    if ( destination.value == "{{ NEW_CAFE }}" ) {

        // Show new destination box and label
        new_destination.style.display = "";
        findLableForControl(new_destination).style.display = "";

    } else {

        // Hide new destination Location
        new_destination.style.display = "none";
        findLableForControl(new_destination).style.display = "none";

    }

    destinationLogic();
    runlogic();
}


// Trap user editing new destination
new_destination.onchange = function() {

    // If they enter a new destination, swap selector to New Cafe
    if ( new_destination.value.trim() != "" ) {
        destination.value = "{{ NEW_CAFE }}";
    }

    destinationLogic();
    runlogic();
}


// Trap user changing the date and auto complete the rest of the form
date.onchange = function() {

    // Autocomplete start time and place
    autoCompleteStart();

    // Run validation tests
    runlogic();

};


// Trap user changing GPX from upload my route to something else
gpx.onchange = function() {

    if ( gpx.value == "{{ UPLOAD_ROUTE }}" ) {

        // Show GPX file upload
        gpx_file.style.display = "";
        findLableForControl(gpx_file).style.display = "";

    } else {

        // Hide GPX file upload
        gpx_file.style.display = "none";
        findLableForControl(gpx_file).style.display = "none";

    }

    gpxLogic();
    runlogic();

}

gpx_file.onchange = function() {
    gpxLogic();
    runlogic();
}


/* ****************************************************************************************************************
                                                 Dialog Form
  **************************************************************************************************************** */


/* Add Dialog to submit button */
document.getElementById("submit").addEventListener("click", function() {
    $('#validate_start').dialog('open');
});


/* Function to run when Add Ride button is pressed */
$(function() {

    /* **************************************************************************
                               Start of Day Settings
    ***************************************************************************** */

    // We might have been called with the date pre-loaded
    if (date.value == "") {

        // Date unset, so:
        // Disable ADD RIDE Button right at the start
        document.getElementById("submit").disabled=true;
        document.getElementById("error").innerHTML="Date has not been set."

         // Hide New Start Location initially
        new_start.style.display = "none";
        findLableForControl(new_start).style.display = "none";

        // Highlight the Date box
        date.style.backgroundColor = '#ffe6e6';

    } else {

        // Date has been set already, so we need to:
        // 1. Autocomplete start details based on the pre-loaded date
        autoCompleteStart();
        // 2. Run all the test logic to see what else needs doing
        runlogic();

    }

    // Highlight GPX file boxes, as they need completing
    gpx.style.backgroundColor = '#ffe6e6';
    gpx_file.style.backgroundColor = '#ffe6e6';

    // Also edit file input to be gpx files only
    gpx_file.setAttribute('accept', '.gpx');

    // Hide New Cafe initially
    new_destination.style.display = "none";
    findLableForControl(new_destination).style.display = "none";


    /* **************************************************************************
                                    Set up Dialog
    ***************************************************************************** */

    $( "#validate_start" ).dialog({
        open: function() {

            if (date.value != "") {

                // date.value has form '2023-11-04', so convert to day of week eg 'Saturday' etc
                let day_of_week = getDayName(date.value);

                // Look up the default start time
                let default_start_time = {{ DEFAULT_START_TIMES | tojson }}[day_of_week];

                // Have they deviated?
                if ( start_time.value == default_start_time['time'] &&
                     meeting_point.value == default_start_time['location'] &&
                     new_start.value == default_start_time['new'] )
                {

                    // All ok - so just go ahead and submit
                    // Close ourself
                    $('#validate_start').dialog('close')

                } else {

                    // Non standard start time
                    document.getElementById("issue").innerHTML =
                        `Start time and / or place looks wrong for <strong>${day_of_week}</strong>? <br>` +
                        `Was expecting: <strong>${default_start_time['time']}</strong> and ` +
                        `<strong>${default_start_time['location']}</strong>. <br>` +
                        `You chose: <strong>${start_time.value}</strong> and ` +
                        `<strong>${meeting_point.value}</strong>. <br><br>` +
                        `Type '<strong>yes</strong>' to confirm your choice.`;

                    // Clear confirm box
                    document.getElementById("confirm").value = "";

                    // Cancel submit
                    // Stop the submit button submitting the form immediately
                    event.preventDefault();
                    // Disable the submit button completely, so they have to use this form
                    document.getElementById("submit").disabled=true;

                };

            } else {

                // Date unset, just fall through to Flask form validation
                $('#validate_start').dialog('close')

            };

        },
        autoOpen: false,
        modal: true,
        width: Math.min(window.innerWidth, 520),
        buttons: [
            {
                // Button 1: cancel
                text: "Cancel",
                "class": 'btn-sm btn-primary',
                click: function() {

                    // Re-enable submit button before we exit
                    document.getElementById("submit").disabled=false;
                    // Close ourself
                    $('#validate_start').dialog('close')

                }
            },
            {
                // Button 2: Confirm their unusual choice
                text: "Confirm",
                "class": 'btn-sm btn-danger float-right',
                click: function() {

                    // Check they entered Yes or derivatives thereof
                    if (document.getElementById("confirm").value.toLowerCase().trim() == 'yes') {

                        // Re-enable submit button before we exit
                        document.getElementById("submit").disabled=false;
                        // Click the submit button to submit the form to the server
                        document.getElementById("submit").click();

                    } else {

                        // Tell them they are an idiot
                        document.getElementById("confirm").value = 'Invalid answer!'

                    }
                }
            }
        ],
       position: {
          my: "center center",
          at: "center center"
       },
    });

});
