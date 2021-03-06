from smoid.languages import Check, CheckCollection, CheckLanguage


class PerlSubroutineCheck (Check):
    def __init__ (self):
        Check.__init__(self)

        self.name = "Perl:Subroutine"
        self.example = "sub do_as_i_say {"
        self.add_language("perl")

        self.add_multiple_matches("(?:^|\n|\r|;)\s*sub\s+([a-zA-Z_][a-zA-Z_0-8]*)\s*{", 10)


class PerlUseCheck (Check):
    def __init__ (self):
        Check.__init__(self)

        self.name = "Perl:Use"
        self.example = "use File::Spec;"
        self.add_language("perl")

        re_ns = "[a-zA-Z_][a-zA-Z_0-9]*"
        re_full_ns = re_ns + "(?:\s*::\s*" + re_ns + ")*"

        self.add_multiple_matches("(?:^|\n|\r|;)\s*use\s*(" + re_full_ns + ")\s*(?:$|\n|\r|;)", 10)


class PerlCheckCollection (CheckCollection):

    def __init__(self):
        self.append(PerlSubroutineCheck())
        self.append(PerlUseCheck())
