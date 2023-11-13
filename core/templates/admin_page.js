
/* ----------------------------------------------------------------------------------------------------
                                        Open page at Events anchor
   ---------------------------------------------------------------------------------------------------- */

{% if anchor == 'messages' %}

    /* Open collapsed section */
    $("#collapseMessageList").collapse('show');

    /* Change button name */
    document.getElementById('show_messages').innerHTML = 'HIDE';

    /* Jump to anchor */
    window.location = (""+window.location).replace(/#[A-Za-z0-9_]*$/,'')+"#{{anchor}}"

{% elif anchor == 'eventLog'%}

    /* Open collapsed section */
    $("#collapseEventList").collapse('show');

    /* Change button name */
    document.getElementById('show_events').innerHTML = 'HIDE';

    /* Jump to anchor */
    window.location = (""+window.location).replace(/#[A-Za-z0-9_]*$/,'')+"#{{anchor}}"

{% endif %}



$(document).ready( function () {


    /* ----------------------------------------------------------------------------------------------------
                                        Activate jQuery on the Tables
       ---------------------------------------------------------------------------------------------------- */

    /* jQuery on our tables where we want dataTables to run */
    $('#trustedUserTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    });

    $('#untrustedUserTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    });

    $('#rideTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#socialTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#blogTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#classifiedTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#commentsTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#eventTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }
    })

    $('#fileTable').DataTable({

        /* Default table length */
        pageLength: 25,

        "autoWidth": false,

        /* "simple_numbers" => 'Previous' and 'Next' buttons, plus page numbers */
        "pagingType": "simple_numbers",

        "oLanguage": {
            "oPaginate": {
                "sFirst": "<<", // This is the link to the first page
                "sPrevious": "<", // This is the link to the previous page
                "sNext": ">", // This is the link to the next page
                "sLast": ">>" // This is the link to the last page
            }
        }

    })



/* ----------------------------------------------------------------------------------------------------
                                          Hide / Show buttons
   ---------------------------------------------------------------------------------------------------- */

    /* Map - Hide <-> Show buttons name change */
    $("#collapseMapControls").on("show.bs.collapse", function(){
        document.getElementById('show_mapcontrols').innerHTML = 'HIDE';
    });
    $("#collapseMapControls").on("hide.bs.collapse", function(){
        document.getElementById('show_mapcontrols').innerHTML = 'SHOW';
    });

    /* Messages - Hide <-> Show buttons name change */
    $("#collapseMessageList").on("show.bs.collapse", function(){
        document.getElementById('show_messages').innerHTML = 'HIDE';
    });
    $("#collapseMessageList").on("hide.bs.collapse", function(){
        document.getElementById('show_messages').innerHTML = 'SHOW';
    });

    /* Admins - Hide <-> Show buttons name change */
    $("#collapseAdminList").on("show.bs.collapse", function(){
        document.getElementById('show_admins').innerHTML = 'HIDE';
    });
    $("#collapseAdminList").on("hide.bs.collapse", function(){
        document.getElementById('show_admins').innerHTML = 'SHOW';
    });

    /* Trusted Users - Hide <-> Show buttons name change */
    $("#collapseTrustedUserList").on("show.bs.collapse", function(){
        document.getElementById('show_trusted_users').innerHTML = 'HIDE';
    });
    $("#collapseTrustedUserList").on("hide.bs.collapse", function(){
        document.getElementById('show_trusted_users').innerHTML = 'SHOW';
    });

    /* Untrusted Users - Hide <-> Show buttons name change */
    $("#collapseUntrustedUserList").on("show.bs.collapse", function(){
        document.getElementById('show_untrusted_users').innerHTML = 'HIDE';
    });
    $("#collapseUntrustedUserList").on("hide.bs.collapse", function(){
        document.getElementById('show_untrusted_users').innerHTML = 'SHOW';
    });

    /* Alerts - Hide <-> Show buttons name change */
    $("#collapseAlertList").on("show.bs.collapse", function(){
        document.getElementById('show_alerts').innerHTML = 'HIDE';
    });
    $("#collapseAlertList").on("hide.bs.collapse", function(){
        document.getElementById('show_alerts').innerHTML = 'SHOW';
    });

    /* Rides - Hide <-> Show buttons name change */
    $("#collapseRideList").on("show.bs.collapse", function(){
        document.getElementById('show_rides').innerHTML = 'HIDE';
    });
    $("#collapseRideList").on("hide.bs.collapse", function(){
        document.getElementById('show_rides').innerHTML = 'SHOW';
    });

    /* Socials - Hide <-> Show buttons name change */
    $("#collapseSocialList").on("show.bs.collapse", function(){
        document.getElementById('show_socials').innerHTML = 'HIDE';
    });
    $("#collapseSocialList").on("hide.bs.collapse", function(){
        document.getElementById('show_socials').innerHTML = 'SHOW';
    });

    /* Blogs - Hide <-> Show buttons name change */
    $("#collapseBlogList").on("show.bs.collapse", function(){
        document.getElementById('show_blogs').innerHTML = 'HIDE';
    });
    $("#collapseBlogList").on("hide.bs.collapse", function(){
        document.getElementById('show_blogs').innerHTML = 'SHOW';
    });

    /* Classifieds - Hide <-> Show buttons name change */
    $("#collapseClassifiedList").on("show.bs.collapse", function(){
        document.getElementById('show_classifieds').innerHTML = 'HIDE';
    });
    $("#collapseClassifiedList").on("hide.bs.collapse", function(){
        document.getElementById('show_classifieds').innerHTML = 'SHOW';
    });

    /* Comments - Hide <-> Show buttons name change */
    $("#collapseCommentsList").on("show.bs.collapse", function(){
        document.getElementById('show_comments').innerHTML = 'HIDE';
    });
    $("#collapseCommentsList").on("hide.bs.collapse", function(){
        document.getElementById('show_comments').innerHTML = 'SHOW';
    });

    /* Events - Hide <-> Show buttons name change */
    $("#collapseEventList").on("show.bs.collapse", function(){
        document.getElementById('show_events').innerHTML = 'HIDE';
    });
    $("#collapseEventList").on("hide.bs.collapse", function(){
        document.getElementById('show_events').innerHTML = 'SHOW';
    });

    /* Files - Hide <-> Show buttons name change */
    $("#collapseFileList").on("show.bs.collapse", function(){
        document.getElementById('show_files').innerHTML = 'HIDE';
    });
    $("#collapseFileList").on("hide.bs.collapse", function(){
        document.getElementById('show_files').innerHTML = 'SHOW';
    });

} );
