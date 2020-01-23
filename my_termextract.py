def itemremover(*items):
    '''
    itemgetterの削除版
    https://docs.python.org/ja/3/library/operator.html#operator.itemgetter
    '''
    def g(obj):
        if hasattr(obj, 'keys'):
            return tuple(obj[key] for key in obj.keys() if key not in items)
        if len(items) == 1:
            if isinstance(obj, str):
                o = list(obj)
                del o[items[0]]
                return ''.join(o)
            else:
                o = list(obj)
                del o[items[0]]
                return tuple(o)
        if isinstance(obj, str):
            return ''.join(o for index, o in enumerate(obj) if index not in items)
        else:
            return tuple(o for index, o in enumerate(obj) if index not in items)
    return g

def format_mecab(text):
    '''
    MeCabで形態素解析したテキストを 1行 9列 になるよう整形する。
    想定している用途　…　改行記号("\n")には 読み と 発音 が付加されないので、その分を"*"を追加する
    
    Input: MeCabで形態素解析したテキスト
    Output: 整形されたテキスト
    '''
    lines = text.split("\n")
    for i in range(len(lines)):
        camma = lines[i].count(",")
        if camma == 0 or camma == 8:
            continue
        elif camma == 6:
            lines[i] = lines[i] + ",*,*"
        else:
            lines[i] = lines[i] + ",*"
    return "\n".join(lines)

def morph_from_mecab(text):
    '''
    MeCabで形態素解析したテキストをtupleに切り分ける。
    1つの形態素を長さ 9 のtupleで表現する。
    (表層系, 品詞, 品詞細分類1, 品詞細分類2, 品詞細分類3, 活用型, 原形, 読み, 発音)
    
    Input: MeCabで形態素解析したテキスト
    Output: 形態素のリスト
    '''
    pattern = re.compile(r'''
                        \n?
                        ([^\t]+?)\t     # 表層系
                        ([^\n\t]*?),    # 品詞
                        ([^\n\t]*?),    # 品詞細分類1
                        ([^\n\t]*?),    # 品詞細分類2
                        ([^\n\t]*?),    # 品詞細分類3
                        ([^\n\t]*?),    # 活用型
                        ([^\n\t]*?),    # 活用形
                        ([^\n\t]*?),    # 原形
                        ([^\n\t]*?),    # 読み
                        ([^\n\t]*?)     # 発音
                        $
                        ''', re.MULTILINE + re.VERBOSE + re.DOTALL)
    
    morphs = pattern.findall(text)
    return morphs

def concat_morph(morphs):
    '''
    複数の形態素の結合を行う。
    結合するのは [表層系, 原形, 読み, 発音] のみ。
    その他はリストの最後の要素に合わせる。
    
    Input: 形態素のリスト
    Output: 結合された形態素
    '''
    import copy
    new_morph = list(copy.deepcopy(morphs[-1]))
    
    # 表層系
    new_morph[0] = "".join(x[0] for x in morphs)
    # 原形
    new_morph[7] = "".join(x[7] for x in morphs if x[7]!="*")
    # 読み
    new_morph[8] = "".join(x[8] for x in morphs if x[8]!="*")
    # 発音
    new_morph[9] = "".join(x[9] for x in morphs if x[9]!="*")
    return tuple(new_morph)

class TermExtract(object):
    '''
    MeCabの形態素解析結果を受け取り、termextractするクラス。
    
    初期化...
    mecab_text = "mecab.parce()で得られたテキスト"
    もしくは、mecab_path = "テキストが保存されたファイルのパス"
    '''
    def __init__(self, mecab_text=None, mecab_path=None):
        if mecab_text is not None:
            self.mecab_text = mecab_text
        else:
            if mecab_path is not None:
                self.read(mecab_path)
            else:
                self.mecab_text = "None"
        
        self.mecab_text = format_mecab(self.mecab_text)
                
        self.extracted_words = []
        self.morphs = []
                
    def read(self, path):
        p = Path(path)
        self.mecab_text = p.read_text()
        
    def get_extracted_words(self):
        import termextract.mecab
        import termextract.core
        from collections import Counter
        
        # 複合語を抽出し、重要度を算出
        frequency = termextract.mecab.cmp_noun_dict(self.mecab_text)
        LR = termextract.core.score_lr(frequency,
                 ignore_words=termextract.mecab.IGNORE_WORDS,
                 lr_mode=1, average_rate=1
             )
        term_imp = termextract.core.term_importance(frequency, LR)

        # 重要度が高い順に並べ替えてリストを返す
        data_collection = Counter(term_imp)
        self.extracted_words = [x[0] for x in data_collection.most_common()]
        return self.extracted_words
    
    def set_extracted_words(self, words):
        self.extracted_words = words
    
    def get_raw_morphs(self):
        return morph_from_mecab(self.mecab_text)
    
    def get_morphs(self):
        if len(self.extracted_words) == 0:
            self.get_extracted_words()
        
        self.morphs = morph_from_mecab(self.mecab_text)
        for cmp_noun in self.extracted_words:
            # 表層系の取得
            surfaces, *_ = zip(*self.morphs)

            # スペースで区切る
            cmp_list = cmp_noun.split(" ")
            len_cmp = len(cmp_list)
            # 連結語でない場合はcontinue
            if len_cmp < 2:
                continue
            
            # 連結語とマッチしたインデックス
            match_indeces = [i for i in range(len(surfaces)-len_cmp+1) if surfaces[i:i+len_cmp]==tuple(cmp_list)]

            # 結合後に削除予定の行のリスト
            drop_list = []
            for idx in match_indeces:
                self.morphs[idx] = concat_morph(self.morphs[idx:idx+len_cmp])
                drop_list.append(list(range(idx+1,idx+len_cmp)))
                
            drop_list = sum(drop_list, [])
            self.morphs = list(itemremover(*drop_list)(self.morphs))
            
        return self.morphs
    
    def get_wakati(self):
        if len(self.morphs) == 0:
            self.get_morphs()

        return " ".join(x[0] for x in self.morphs)
    
    def get_modified_mecab_text(self):
        '''
        termextractによって抽出された単語を連結し、をMeCabと同じ形式のテキストを返す。
        Output: MeCabと同じ形式のテキスト
        '''
        if len(self.morphs) == 0:
            self.get_morphs()
            
        return "\n".join(f"{surface}\t" + ",".join(other) for surface, *other in self.morphs) + "\nEOS\n"
    
if __name__ == "__main__":
    import MeCab
    text = "羅生門が、朱雀大路にある以上は、この男のほかにも、雨やみをする市女笠や揉烏帽子が、もう二三人はありそうなものである。"

    mecab = MeCab.Tagger()
    mecab_text = mecab.parse(text)
    
    # MeCabの結果を渡す
    TX = TermExtract(mecab_text)
    extracted = TX.get_extracted_words()  # 重要な語を抽出
    modified_text = TX.get_modified_mecab_text()  # 重要な語を元に単語を連結したテキスト
    
    # 結果の比較
    print(extracted, "\n")
    print(mecab_text)
    print(modified_text)
