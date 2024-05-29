from games.minecraft.utils.extract_similar_action import ExtractSimilarAction


class PrepareSamples:
    def __init__(self):
        self.esa = ExtractSimilarAction()

    def getsamples(self, dialogue):
        samples = {}
        for turn, data in dialogue.items():
            samples[turn] = self.esa.get_similar_dialog_with_action(data['utterance'])
        return samples