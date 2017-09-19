// Askbot adapter to markdown converter;
var getAskbotMarkdownConverter = function() {
    askbot['controllers'] = askbot['controllers'] || {};
    var converter = askbot['controllers']['markdownConverter'];
    if (!converter) {
        converter = new AskbotMarkdownConverter();
        askbot['controllers']['markdownConverter'] = converter;
    }
    return converter;
};

var AskbotMarkdownConverter = function() {
    this._converter = new Markdown.getSanitizingConverter();
    this._timeout = null;
};

AskbotMarkdownConverter.prototype.scheduleMathJaxRendering = function () {
    if (this._timeout) {
        clearTimeout(this._timeout);
    }
    var renderFunc = function () {
        // for previews
        var previewers = document.getElementsByClassName("wmd-preview")
        for (var i=0; i<previewers.length; i++){
            MathJax.Hub.Queue(['Typeset', MathJax.Hub, previewers[i]]);
        }

        // for question and answer posts
        var posts = document.getElementsByClassName("js-editable-content")
        for (var i=0; i<posts.length; i++){
            MathJax.Hub.Queue(['Typeset', MathJax.Hub, posts[i]]);
        }

        // for expanded posts
        var anssnippets = document.getElementsByClassName("snippet")
        for (var i=0; i<anssnippets.length; i++){
            MathJax.Hub.Queue(['Typeset', MathJax.Hub, anssnippets[i]]);
        }
    };
    this._timeout = setTimeout(renderFunc, 500);
};

AskbotMarkdownConverter.prototype.makeHtml = function (text) {
    var makeHtmlBase = this._converter.makeHtml;
    if (askbot['settings']['mathjaxEnabled'] === false){
        return makeHtmlBase(text);
    } else if (typeof MathJax != 'undefined') {
        MathJax.Hub.queue.Push(
            function(){
                $('#previewer').html(makeHtmlBase(text));
            }
        );
        this.scheduleMathJaxRendering();
        return $('#previewer').html();
    } else {
        console.log('Could not load MathJax');
        return makeHtmlBase(text);
    }
};
