#include "HoverGunRig.h"

FName UHoverGunRig::NormalizeWeaponKey(FName DefinitionName)
{
    // String form: FName keeps a trailing _N as its number part, so _3 and _001 must be read as text.
    const FString Name = DefinitionName.ToString();
    int32 Split = INDEX_NONE;
    if (!Name.FindLastChar(TEXT('_'), Split) || Split <= 0 || Split == Name.Len() - 1)
        return DefinitionName;
    for (int32 Index = Split + 1; Index < Name.Len(); ++Index)
        if (!FChar::IsDigit(Name[Index]))
            return DefinitionName;
    return FName(*Name.Left(Split));
}
