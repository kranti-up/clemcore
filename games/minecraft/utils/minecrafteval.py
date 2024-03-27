import re

class MinecraftEval:
    def __init__(self):
        pass

    def _find_coordinate_points(self, line, pattern):
        if pattern in line:
            pt = line.split(pattern)[1].strip()
            #print('After first split',pt)
            if ',' in pt:
                pt = pt.split(',')[0]
            else:
                #For Z axis
                #print('No comma found')
                if ')' in pt:
                    pt = pt.split(')')[0]
                else:
                    #print('No closing bracket found')
                    return None
            if pt.isdigit():
                return int(pt)
            else:
                #For color
                #if pt.isalpha() and pattern == 'color=':
                if pattern == 'color=':
                    return pt.strip()
                else:
                    if pt.startswith('-') or pt.startswith('+'):
                        #Handling negative numbers!
                        try:
                            return int(pt)
                        except:
                            print('Error in line, skipping',line)
                return None


    def _get_minecraft_format(self, code):
        code = re.findall('p.*?\(.*?\)', code.strip())
        conv_format = set()

        for line in code:
            #print(line)
            line = line.strip()
            if 'color=' in line and 'x=' in line and 'y=' in line and 'z=' in line:
                c = self._find_coordinate_points(line, 'color=')
                x = self._find_coordinate_points(line, 'x=')
                y = self._find_coordinate_points(line, 'y=')
                z = self._find_coordinate_points(line, 'z=')
                if(any(i is None for i in [c, x, y, z])):
                    print('Skipping line: ', line, [c, x, y, z])
                    continue
                else:
                    if line.startswith("pick"):
                        #Removal
                        action_tuple = ('action_type', 'removal')
                    elif line.startswith("place"):
                        #Placement
                        action_tuple = ('action_type', 'placement')
                    else:
                        #Wrong command
                        continue
                    color_tuple = ('type', c)
                    axis_tuple = ('x', x), ('y', y), ('z', z)
                    conv_format.add((action_tuple, color_tuple, axis_tuple))
        return conv_format    

    def compute_fn_fp_tp(self, gtruth_code, response_code):
        gtruth_code_mc = self._get_minecraft_format(gtruth_code)
        #print("gtruth_code_mc\n",gtruth_code_mc)
        if ":" in response_code:
            response_code = response_code.split(":")[1]
            response_code = response_code.strip()
        response_code_mc = self._get_minecraft_format(response_code)
        #print("response_code_mc\n",response_code_mc)
        tp, fp, fn = 0, 0, 0
        fn = len(gtruth_code_mc - response_code_mc)
        #print("fn\n",fn)
        fp = len(response_code_mc - gtruth_code_mc)
        #print("fp\n",fp)
        tp = len(response_code_mc & gtruth_code_mc)
        #print("tp\n",tp)
        return fn, fp, tp    
    

if __name__=="__main__":
    gtruth_code = "pick(color='red',x=0,y=2,z=-1)"
    response_code = "pick(color='red', x=0, y=2, z=0)"
    me = MinecraftEval()
    fn, fp, tp = me.compute_fn_fp_tp(gtruth_code, response_code)
    print(fn, fp, tp)