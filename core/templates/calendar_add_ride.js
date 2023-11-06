// JS Module for validating ride entry

// The four form elements we need
let date = document.getElementById('date');
let start_time = document.getElementById('start_time');
let meeting_point = document.getElementById('start_location');
let new_start = document.getElementById('other_location');

// Get day of week from date
function getDayName(dateStr)
    {
        var date = new Date(dateStr);
        return date.toLocaleDateString('en-GB', { weekday: 'long' });
    }

// Trap user changing the date and auto complete the rest of the form
date.onchange = function() {

    // date.value has form '2023-11-04', so convert to day of week eg 'Saturday' etc
    let day_of_week = getDayName(date.value);

    // Look up the default start time
    let default_start_time = {{ DEFAULT_START_TIMES | tojson }}[day_of_week]

    // Populate the form
    start_time.value = default_start_time['time'];
    meeting_point.value = default_start_time['location'];
    new_start.value = default_start_time['new'];

};


/* Add Dialog to submit button */
document.getElementById("submit").addEventListener("click", function()
    {
        $('#validate_start').dialog('open');
    }
);

/* Function to validate the start time */
$(function() {
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
        width: 520,
        buttons: [
            {
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
                text: "Confirm",
                "class": 'btn-sm btn-danger float-right',
                click: function() {

                    // Get value of text box
                    if (document.getElementById("confirm").value.toLowerCase() == 'yes') {
                        // Go ahead
                        // Re-enable submit button before we exit
                        document.getElementById("submit").disabled=false;

                        // Click the submit button
                        document.getElementById("submit").click();
                    } else {
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
