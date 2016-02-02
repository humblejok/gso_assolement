var urlParams;
(window.onpopstate = function () {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1);

    urlParams = {};
    while (match = search.exec(query))
       urlParams[decode(match[1])] = decode(match[2]);
})();

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

$.ajaxSetup({
    cache: false,
    crossDomain: false, // Avoid cross-domain forgery
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type)) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
        
    }
});

$.fn.hasAttr = function(attributeName) {
    var attribute = $(this).attr(attributeName);
    if (typeof attribute !== typeof undefined && attribute !== false) {
        return true;
    } else {
        return false;
    }
}


$.fn.serializeJSON = function(trim) {
    var result = {};
    var as_array = this.serializeArray();
    $.each(as_array, function () {
        var wrkName = trim?this.name.replaceAll(trim,''):this.name;
        if (result[wrkName] !== undefined) {
            if (!result[wrkName].push) {
                result[wrkName] = [result[wrkName]];
            }
            result[wrkName].push(this.value || '');
        } else {
            result[wrkName] = this.value || '';
        }
    });
    return result;
};

$.fn.serializeForm = function(trim) {
    var newForm = new FormData();
    var data = this.serializeJSON(trim);
    $.each(data, function(key, value){
        newForm.append(key.toString(),value);
    });
    return newForm;
}

function serializeDict(data) {
    var newForm = new FormData();
    $.each(data, function(key, value){
        newForm.append(key.toString(),value);
    });
    return newForm;
}

String.prototype.replaceAll = function(search, replace) {
    if (replace === undefined) {
        return this.toString();
    }
    return this.split(search).join(replace);
}

function getPropertyFromString(object, propertyField) {
    var fields = propertyField.split(".");
    while(fields.length && (object = object[fields.shift()]));
    return object;
}

// http://stackoverflow.com/questions/3885817/how-to-check-that-a-number-is-float-or-integer
function isInt(n){
    return Number(n) === n && n % 1 === 0;
}

function isFloat(n){
    return n === Number(n) && n % 1 !== 0;
}


// http://stackoverflow.com/questions/2901102/how-to-print-a-number-with-commas-as-thousands-separators-in-javascript
function numberWithCommas(x) {
    var parts = x.toString().split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
}

// amCHARTS definition
var amBackground = "#D8E0EC";
var amColors = ["#0065A4", "#3683B6","#6CA1C8", "#A2BFDA"];