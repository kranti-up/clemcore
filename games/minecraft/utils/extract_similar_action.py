import pickle
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class ExtractSimilarAction:
    def __init__(self, train_embeddings_pickle = "/home/admin/Desktop/codebase/cocobots/detectobject_code/clembench/games/minecraft/resources/embeds/sent_transf_embeddings_train.pickle"):
        self.action_embeddings_train = ""
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.read_embeddings(train_embeddings_pickle)


    def read_embeddings(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.action_embeddings_train = pickle.load(f)
        except FileNotFoundError:
            print('No embeddings file found. Please run minecraft_dialog_embeddings.py first.')      
                
    def get_embeddings(self, dialog):
        if not dialog:
            return None
        return self.model.encode(dialog)

    def get_similar_dialog_with_action(self, dialog):
        if not self.action_embeddings_train:
            self.read_embeddings()
        #print('received dialog: ',dialog, '\n')
        dialog_embeddings = self.get_embeddings(dialog)
        #print('dialog embeddings: ',dialog_embeddings.shape, '\n')
        similar_dialog_dict = {}
        sorted_similar_dialog_dict = {}
        for embed_action in self.action_embeddings_train:
            #print(embed_action[0], embed_action[1].shape, embed_action[2])
            similarity = cosine_similarity([dialog_embeddings], [embed_action[1]])[0][0]
            #print(similarity)
            #if similarity > 0.8:
            similar_dialog_dict[similarity] = embed_action
                #print('Similarity Score: ',similarity)
                #print('matched dialog: ',embed_action[0])
                #print('action: ',embed_action[2],'\n')
        sorted_similar_dialog_dict = sorted(similar_dialog_dict.items(), reverse=True)
        #print("Similar Dialog Dict Length: ",len(similar_dialog_dict.keys()))
        similar_action_pair_list = []
        for k, v in sorted_similar_dialog_dict[:3]:
            #print(k, v[0],'\n',v[2],'\n')
            #print("Similarity Score: ",k)
            similar_action_pair_list.append([v[0], v[2]])
        return similar_action_pair_list

if __name__ == '__main__':
    esa = ExtractSimilarAction()
    dialog = "Now add a yellow brick to the right of the top of the neck"

    print(esa.get_similar_dialog_with_action(dialog))